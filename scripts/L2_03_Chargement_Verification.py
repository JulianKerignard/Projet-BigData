#!/usr/bin/env python3
"""
L2 - Chargement Fait_Hospitalisation + Vérification
Task: [P2] Chargement Fait_Hospitalisation + vérification

Load cleaned hospitalisations data into fact table and validate
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from datetime import datetime, timedelta
import sys

# Initialize Spark
spark = SparkSession.builder \
    .appName("L2_Loading_Fait_Hospitalisation") \
    .config("spark.sql.shuffle.partitions", "8") \
    .config("hive.exec.dynamic.partition.mode", "nonstrict") \
    .enableHiveSupport() \
    .getOrCreate()

print("=" * 80)
print("L2 - LOADING FAIT_HOSPITALISATION")
print("=" * 80)

# ============================================================================
# STAGE 1: READ CLEANED DATA
# ============================================================================

print("\n📥 STAGE 1: READING CLEANED DATA")

df_cleaned = spark.read.parquet("data/staging/hospitalisations_cleaned")
print(f"✓ Loaded {df_cleaned.count()} rows from staging")

# ============================================================================
# STAGE 2: ENRICH WITH DIMENSIONS
# ============================================================================

print("\n🔗 STAGE 2: DIMENSION LOOKUPS")

# Load dimensions
dim_temps = spark.sql("SELECT * FROM Dim_Temps").cache()
dim_patient = spark.sql("SELECT * FROM Dim_Patient").cache()
dim_etablissement = spark.sql("SELECT * FROM Dim_Etablissement").cache()
dim_diagnostic = spark.sql("SELECT * FROM Dim_Diagnostic").cache()
dim_type_sejour = spark.sql("SELECT * FROM Dim_Type_Sejour").cache()

# Lookup Dim_Temps
df_with_temps = df_cleaned.join(
    dim_temps.select("id_temps", "date_entree", "annee"),
    on="date_entree",
    how="left"
).withColumnRenamed("annee", "annee_entree")

print(f"✓ Temps: {df_with_temps.filter(col('id_temps').isNotNull()).count()} matched")

# Lookup Dim_Patient (with pseudonymization)
df_with_patient = df_with_temps.join(
    dim_patient.select("id_patient", "id_patient_original"),
    on=col("Id_patient") == col("id_patient_original"),
    how="left"
).drop("id_patient_original")

print(f"✓ Patient: {df_with_patient.filter(col('id_patient').isNotNull()).count()} matched")

# Lookup Dim_Etablissement
df_with_etab = df_with_patient.join(
    dim_etablissement.select("id_etablissement", "code_finess"),
    on=col("identifiant_organisation") == col("code_finess"),
    how="left"
).drop("code_finess")

match_etab = df_with_etab.filter(col('id_etablissement').isNotNull()).count()
print(f"✓ Etablissement: {match_etab} matched ({match_etab/df_with_etab.count()*100:.1f}%)")

# Lookup Dim_Diagnostic
df_with_diag = df_with_etab.join(
    dim_diagnostic.select("id_diagnostic", "code_cim10"),
    on=col("Code_diagnostic") == col("code_cim10"),
    how="left"
).drop("code_cim10").fillna({'id_diagnostic': -1})  # -1 for unknown

print(f"✓ Diagnostic: matched (unknown = -1)")

# Determine Type_Sejour based on length of stay
df_with_sejour = df_with_diag.withColumn(
    "type_sejour_calc",
    when(col("Jour_Hospitalisation") < 1, "Ambulatoire")
    .when(col("Jour_Hospitalisation").between(1, 2), "Court séjour")
    .otherwise("Séjour standard")
).join(
    dim_type_sejour.select("id_type_sejour", "libelle_type"),
    on=col("type_sejour_calc") == col("libelle_type"),
    how="left"
).drop("type_sejour_calc", "libelle_type")

print(f"✓ Type_Sejour: matched")

# ============================================================================
# STAGE 3: DATA TRANSFORMATIONS
# ============================================================================

print("\n🔄 STAGE 3: TRANSFORMATIONS")

df_transformed = df_with_sejour.select(
    # Dimension FKs
    col("id_temps").cast("INT").alias("id_temps"),
    col("id_patient").cast("INT").alias("id_patient"),
    col("id_etablissement").cast("INT").alias("id_etablissement"),
    col("id_diagnostic").cast("INT").alias("id_diagnostic"),
    col("id_type_sejour").cast("INT").alias("id_type_sejour"),

    # Degenerate dimensions
    col("Num_Hospitalisation").alias("num_hospitalisation_pseudo"),
    col("date_entree").cast("DATE").alias("date_entree"),
    (col("date_entree") + col("Jour_Hospitalisation")).alias("date_sortie"),
    lit("Sortie standard").alias("motif_sortie"),

    # Measures
    lit(1).alias("nb_hospitalisations"),
    col("Jour_Hospitalisation").cast("INT").alias("nb_jours_hospitalisation"),
    col("Jour_Hospitalisation").cast("DECIMAL(7,2)").alias("dmos"),
    lit(None).cast("DECIMAL(12,2)").alias("cout_estime"),

    # Flags
    lit(False).alias("est_readmission"),  # Will be computed separately
    lit(False).alias("est_deces"),         # Will be enriched with deces table
    lit(False).alias("est_sortie_contre_avis"),

    # Audit
    current_timestamp().alias("date_chargement"),
    current_timestamp().alias("date_modification"),
    lit("hospitalisations.csv").alias("source_data"),

    # Partition column
    col("annee_entree").cast("INT").alias("annee_entree")
)

print(f"✓ Transformed schema created: {len(df_transformed.columns)} columns")

# ============================================================================
# STAGE 4: DETECT READMISSIONS
# ============================================================================

print("\n🔍 STAGE 4: READMISSION DETECTION")

# Window function: check if there's a previous hospitalization within 30 days
window_spec = Window.partitionBy("id_patient").orderBy("date_entree")

df_with_readmissions = df_transformed.withColumn(
    "prev_date_sortie",
    lag("date_sortie").over(window_spec)
).withColumn(
    "est_readmission",
    when(
        (col("prev_date_sortie").isNotNull()) &
        (col("date_entree") <= col("prev_date_sortie") + lit(30)) &
        (col("date_entree") > col("prev_date_sortie")),
        True
    ).otherwise(False)
).drop("prev_date_sortie")

readmissions = df_with_readmissions.filter(col("est_readmission")).count()
print(f"✓ Readmissions detected: {readmissions} ({readmissions/df_with_readmissions.count()*100:.2f}%)")

# ============================================================================
# STAGE 5: ENRICH WITH DEATH DATA
# ============================================================================

print("\n☠️  STAGE 5: DEATH ENRICHMENT")

# Load death registry and check if patient died during or shortly after admission
deces = spark.sql("""
    SELECT
        id_patient_pseudo,
        date_deces
    FROM deces
    WHERE date_deces IS NOT NULL
""")

df_with_deaths = df_with_readmissions.join(
    deces,
    on=col("id_patient") == col("id_patient_pseudo"),
    how="left"
).withColumn(
    "est_deces",
    when(
        (col("date_deces").isNotNull()) &
        (col("date_deces") >= col("date_entree")) &
        (col("date_deces") <= col("date_sortie") + lit(30)),
        True
    ).otherwise(False)
).drop("date_deces", "id_patient_pseudo")

deaths = df_with_deaths.filter(col("est_deces")).count()
print(f"✓ Deaths detected: {deaths} ({deaths/df_with_deaths.count()*100:.2f}%)")

# ============================================================================
# STAGE 6: LOAD INTO FACT TABLE
# ============================================================================

print("\n💾 STAGE 6: LOADING INTO FACT TABLE")

df_fact = df_with_deaths.select(
    "id_temps", "id_patient", "id_etablissement", "id_diagnostic", "id_type_sejour",
    "num_hospitalisation_pseudo", "date_entree", "date_sortie", "motif_sortie",
    "nb_hospitalisations", "nb_jours_hospitalisation", "dmos", "cout_estime",
    "est_readmission", "est_deces", "est_sortie_contre_avis",
    "date_chargement", "date_modification", "source_data", "annee_entree"
)

# Write to fact table (overwrite mode for initial load)
df_fact.write \
    .format("hive") \
    .mode("overwrite") \
    .option("path", "/warehouse/fait_hospitalisation") \
    .partitionBy("annee_entree") \
    .bucketBy(8, "id_patient") \
    .sortBy("id_patient") \
    .saveAsTable("Fait_Hospitalisation")

rows_loaded = spark.sql("SELECT COUNT(*) as cnt FROM Fait_Hospitalisation").collect()[0][0]
print(f"✓ Loaded {rows_loaded} rows into Fait_Hospitalisation")

# ============================================================================
# STAGE 7: VALIDATION & QUALITY CHECKS
# ============================================================================

print("\n✅ STAGE 7: VALIDATION & QUALITY CHECKS")

# Check 1: Row count consistency
check1 = spark.sql("""
    SELECT
        'Row Count' as check_name,
        COUNT(*) as total_rows,
        COUNT(DISTINCT id_patient) as nb_unique_patients,
        COUNT(DISTINCT id_etablissement) as nb_unique_facilities
    FROM Fait_Hospitalisation
""").collect()[0]

print(f"\n  Row Count:")
print(f"    Total rows:        {check1[1]}")
print(f"    Unique patients:   {check1[2]}")
print(f"    Unique facilities: {check1[3]}")

# Check 2: Key validation
check2 = spark.sql("""
    SELECT
        SUM(CASE WHEN id_temps IS NULL THEN 1 ELSE 0 END) as null_temps,
        SUM(CASE WHEN id_patient IS NULL THEN 1 ELSE 0 END) as null_patient,
        SUM(CASE WHEN id_etablissement IS NULL THEN 1 ELSE 0 END) as null_etab,
        SUM(CASE WHEN nb_jours_hospitalisation < 0 THEN 1 ELSE 0 END) as negative_days
    FROM Fait_Hospitalisation
""").collect()[0]

print(f"\n  Key Validation:")
print(f"    NULL id_temps:      {check2[0]} {'❌' if check2[0] > 0 else '✅'}")
print(f"    NULL id_patient:    {check2[1]} {'❌' if check2[1] > 0 else '✅'}")
print(f"    NULL id_etab:       {check2[2]} {'❌' if check2[2] > 0 else '✅'}")
print(f"    Negative days:      {check2[3]} {'❌' if check2[3] > 0 else '✅'}")

# Check 3: Date validation
check3 = spark.sql("""
    SELECT
        COUNT(*) as invalid_dates
    FROM Fait_Hospitalisation
    WHERE date_sortie IS NOT NULL AND date_entree > date_sortie
""").collect()[0]

print(f"\n  Date Validation:")
print(f"    Entry > Exit dates: {check3[0]} {'❌' if check3[0] > 0 else '✅'}")

# Check 4: Measure validation
check4 = spark.sql("""
    SELECT
        COUNT(*) as invalid_measures
    FROM Fait_Hospitalisation
    WHERE nb_hospitalisations != 1 OR nb_jours_hospitalisation IS NULL
""").collect()[0]

print(f"\n  Measure Validation:")
print(f"    Invalid measures:   {check4[0]} {'❌' if check4[0] > 0 else '✅'}")

# Check 5: Dimension match rates
check5 = spark.sql("""
    SELECT
        ROUND(COUNT(CASE WHEN id_temps IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 2) as match_rate_temps,
        ROUND(COUNT(CASE WHEN id_patient IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 2) as match_rate_patient,
        ROUND(COUNT(CASE WHEN id_etablissement IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 2) as match_rate_etab,
        ROUND(COUNT(CASE WHEN id_diagnostic IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 2) as match_rate_diag
    FROM Fait_Hospitalisation
""").collect()[0]

print(f"\n  Dimension Match Rates:")
print(f"    Dim_Temps:        {check5[0]}%")
print(f"    Dim_Patient:      {check5[1]}%")
print(f"    Dim_Etablissement: {check5[2]}%")
print(f"    Dim_Diagnostic:   {check5[3]}%")

# Check 6: Distribution by partition
check6 = spark.sql("""
    SELECT
        annee_entree,
        COUNT(*) as nb_rows,
        COUNT(DISTINCT id_patient) as nb_patients
    FROM Fait_Hospitalisation
    GROUP BY annee_entree
    ORDER BY annee_entree DESC
""").collect()

print(f"\n  Data Distribution by Year:")
for row in check6:
    print(f"    {row[0]}: {row[1]:,} rows, {row[2]:,} patients")

# ============================================================================
# AUDIT LOGGING
# ============================================================================

print("\n📝 STAGE 8: AUDIT LOGGING")

audit_record = {
    "timestamp": datetime.now().isoformat(),
    "job_name": "L2_Loading_Fait_Hospitalisation",
    "rows_loaded": rows_loaded,
    "rows_source": df_cleaned.count(),
    "match_rate_temps": check5[0],
    "match_rate_patient": check5[1],
    "match_rate_etab": check5[2],
    "match_rate_diag": check5[3],
    "readmissions_detected": readmissions,
    "deaths_detected": deaths,
    "validation_status": "PASSED" if (check2[0] == 0 and check2[1] == 0 and check3[0] == 0) else "FAILED"
}

# Insert into audit table
spark.sql(f"""
    INSERT INTO audit_fait_hospitalisation
    VALUES (
        NULL,
        'INSERT',
        {rows_loaded},
        FROM_UNIXTIME(UNIX_TIMESTAMP()),
        'etl_process',
        'Batch load from hospitalisations.csv',
        'Status: {audit_record["validation_status"]}'
    )
""")

print(f"✓ Audit record created: {audit_record['validation_status']}")

# ============================================================================
# FINAL SUMMARY
# ============================================================================

print("\n" + "=" * 80)
print("✅ LOADING COMPLETED SUCCESSFULLY")
print("=" * 80)

print(f"\n📊 SUMMARY:")
print(f"  Source rows:        {df_cleaned.count():,}")
print(f"  Loaded rows:        {rows_loaded:,}")
print(f"  Readmissions:       {readmissions}")
print(f"  Deaths detected:    {deaths}")
print(f"  Match rate temps:   {check5[0]}%")
print(f"  Match rate patient: {check5[1]}%")
print(f"  Validation:         {audit_record['validation_status']}")

sys.exit(0 if audit_record['validation_status'] == 'PASSED' else 1)
