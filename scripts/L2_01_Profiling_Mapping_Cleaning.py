#!/usr/bin/env python3
"""
L2 - Profiling, Mapping & Cleaning - Hospitalisations
Task: [P2] Profiling + mapping + cleaning Hospitalisations

Analyze source data structure, identify issues, and prepare for loading
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
import pandas as pd
from datetime import datetime

# Initialize Spark
spark = SparkSession.builder \
    .appName("L2_Profiling_Hospitalisations") \
    .config("spark.sql.shuffle.partitions", "8") \
    .getOrCreate()

# ============================================================================
# STAGE 1: LOAD RAW DATA
# ============================================================================

print("=" * 80)
print("STAGE 1: DATA LOADING & INITIAL PROFILING")
print("=" * 80)

# Load CSV with inferred schema
df_raw = spark.read \
    .option("delimiter", ";") \
    .option("header", "true") \
    .option("encoding", "UTF-8") \
    .option("inferSchema", "true") \
    .csv("data/raw/Hospitalisations.csv")

print(f"\n✓ Loaded {df_raw.count()} rows")
print(f"✓ Columns: {', '.join(df_raw.columns)}")

# ============================================================================
# STAGE 2: DATA PROFILING
# ============================================================================

print("\n" + "=" * 80)
print("STAGE 2: DATA PROFILING")
print("=" * 80)

# Schema and types
print("\n📋 SCHEMA:")
df_raw.printSchema()

# Row count and null analysis
print("\n🔍 NULL VALUES & COMPLETENESS:")
null_counts = df_raw.select([
    count(when(col(c).isNull(), 1)).alias(c)
    for c in df_raw.columns
]).collect()[0]

for col_name in df_raw.columns:
    null_count = null_counts[col_name]
    total_rows = df_raw.count()
    pct = (null_count / total_rows * 100) if total_rows > 0 else 0
    status = "✅" if pct < 5 else "⚠️ " if pct < 20 else "❌"
    print(f"  {status} {col_name:40} NULL: {null_count:5} ({pct:5.1f}%)")

# Duplicates analysis
print("\n🔄 DUPLICATE DETECTION:")
total_rows = df_raw.count()
distinct_rows = df_raw.dropDuplicates().count()
dup_count = total_rows - distinct_rows
print(f"  Total rows:     {total_rows}")
print(f"  Distinct rows:  {distinct_rows}")
print(f"  Duplicates:     {dup_count} ({dup_count/total_rows*100:.1f}%)")

# Check for duplicates by key (Id_patient, Num_Hospitalisation, Date_Entree)
if "Id_patient" in df_raw.columns and "Num_Hospitalisation" in df_raw.columns:
    dup_by_key = df_raw.groupBy("Id_patient", "Num_Hospitalisation", "Date_Entree") \
        .count().filter(col("count") > 1).count()
    print(f"  Duplicates by (Patient, Hosp#, Date): {dup_by_key}")

# Data type analysis
print("\n🏷️  DATA TYPES:")
for field in df_raw.schema.fields:
    print(f"  {field.name:40} {field.dataType}")

# Sample data
print("\n📊 SAMPLE DATA (first 5 rows):")
df_raw.show(5, truncate=False)

# ============================================================================
# STAGE 3: COLUMN-LEVEL ANALYSIS
# ============================================================================

print("\n" + "=" * 80)
print("STAGE 3: COLUMN-LEVEL ANALYSIS")
print("=" * 80)

# Numeric columns statistics
numeric_cols = ["Id_patient", "Jour_Hospitalisation"]
for col_name in numeric_cols:
    if col_name in df_raw.columns:
        print(f"\n📈 {col_name}:")
        stats = df_raw.describe(col_name).collect()
        for row in stats:
            print(f"  {row[0]:15} {row[1]}")

# String columns - unique values
print("\n📝 STRING COLUMNS - UNIQUE VALUES:")
string_cols = ["identifiant_organisation", "Code_diagnostic"]
for col_name in string_cols:
    if col_name in df_raw.columns:
        unique_count = df_raw.select(col_name).distinct().count()
        print(f"  {col_name:40} {unique_count} unique values")
        # Show top 10
        df_raw.groupBy(col_name).count().orderBy(desc("count")).show(10, truncate=False)

# Date column analysis
print("\n📅 DATE ANALYSIS - Date_Entree:")
date_samples = df_raw.select("Date_Entree").distinct().limit(20).collect()
print(f"  Sample values: {[row[0] for row in date_samples]}")

# ============================================================================
# STAGE 4: DATA QUALITY ISSUES
# ============================================================================

print("\n" + "=" * 80)
print("STAGE 4: DATA QUALITY ISSUES & VALIDATION")
print("=" * 80)

issues = []

# Issue 1: Null mandatory fields
mandatory_fields = ["Id_patient", "Num_Hospitalisation", "Date_Entree", "identifiant_organisation"]
for field in mandatory_fields:
    if field in df_raw.columns:
        null_count = df_raw.filter(col(field).isNull()).count()
        if null_count > 0:
            issues.append(f"❌ {null_count} NULL values in mandatory field '{field}'")
            print(f"  ❌ {null_count} NULL values in '{field}'")

# Issue 2: Invalid date format
print("\n  🔍 Date format validation (Date_Entree):")
# Try to parse dates
df_with_parsed_date = df_raw.withColumn(
    "date_parsed",
    to_date(col("Date_Entree"), "dd/MM/yyyy")
)
unparseable_dates = df_with_parsed_date.filter(col("date_parsed").isNull()).count()
if unparseable_dates > 0:
    issues.append(f"❌ {unparseable_dates} dates cannot be parsed (invalid format)")
    print(f"     ❌ {unparseable_dates} dates with unparseable format")
    df_raw.filter(col("Date_Entree").rlike("^[0-9]{2}/[0-9]{2}/[0-9]{4}$") == False) \
        .select("Date_Entree").distinct().show(10)
else:
    print(f"     ✅ All dates are in DD/MM/YYYY format")

# Issue 3: Negative or zero days
print("\n  🔍 Jour_Hospitalisation validation:")
negative_days = df_raw.filter(col("Jour_Hospitalisation") < 0).count()
if negative_days > 0:
    issues.append(f"❌ {negative_days} negative jour_hospitalisation values")
    print(f"     ❌ {negative_days} negative values found")

zero_days = df_raw.filter(col("Jour_Hospitalisation") == 0).count()
if zero_days > 0:
    print(f"     ⚠️  {zero_days} zero values (ambulatory cases?)")

# ============================================================================
# STAGE 5: MAPPING SPECIFICATION
# ============================================================================

print("\n" + "=" * 80)
print("STAGE 5: COLUMN MAPPING SPECIFICATION")
print("=" * 80)

mapping = {
    "Num_Hospitalisation": {
        "target": "Num_Hospitalisation_pseudo",
        "type": "VARCHAR",
        "transform": "Hash(SHA-256) + salt",
        "reason": "PII - anonymize"
    },
    "Id_patient": {
        "target": "Id_patient_pseudo",
        "type": "INT",
        "transform": "Hash(SHA-256) + salt → lookup mapping table",
        "reason": "PII - pseudonymize"
    },
    "identifiant_organisation": {
        "target": "id_etablissement",
        "type": "INT",
        "transform": "Lookup Dim_Etablissement",
        "reason": "Foreign key to facility"
    },
    "Code_diagnostic": {
        "target": "id_diagnostic",
        "type": "INT",
        "transform": "Lookup Dim_Diagnostic, default 'UNKNOWN' if null",
        "reason": "Foreign key to diagnosis"
    },
    "Suite_diagnostic_consultation": {
        "target": "DROPPED",
        "type": "VARCHAR",
        "transform": "Delete",
        "reason": "Redundant with Code_diagnostic + identifiable"
    },
    "Date_Entree": {
        "target": "date_entree, id_temps",
        "type": "DATE, INT",
        "transform": "Parse DD/MM/YYYY → DATE, then lookup Dim_Temps",
        "reason": "Temporal dimension key"
    },
    "Jour_Hospitalisation": {
        "target": "nb_jours_hospitalisation, dmos",
        "type": "INT, DECIMAL",
        "transform": "Direct copy + ensure >= 0",
        "reason": "Measure/fact"
    }
}

print("\n🔄 MAPPING RULES:")
for source, spec in mapping.items():
    print(f"\n  {source}")
    print(f"    → Target: {spec['target']}")
    print(f"    → Transform: {spec['transform']}")
    print(f"    → Reason: {spec['reason']}")

# ============================================================================
# STAGE 6: CLEANING LOGIC
# ============================================================================

print("\n" + "=" * 80)
print("STAGE 6: CLEANING & TRANSFORMATION LOGIC")
print("=" * 80)

df_cleaned = df_raw

# Remove rows with mandatory null fields
df_cleaned = df_cleaned.filter(
    (col("Id_patient").isNotNull()) &
    (col("Date_Entree").isNotNull()) &
    (col("identifiant_organisation").isNotNull()) &
    (col("Num_Hospitalisation").isNotNull())
)

print(f"\n✓ After removing NULL mandatory fields: {df_cleaned.count()} rows")

# Remove duplicates
df_cleaned = df_cleaned.dropDuplicates(["Id_patient", "Num_Hospitalisation", "Date_Entree"])
print(f"✓ After removing duplicates: {df_cleaned.count()} rows")

# Parse dates
df_cleaned = df_cleaned.withColumn(
    "date_entree_parsed",
    to_date(col("Date_Entree"), "dd/MM/yyyy")
)

# Filter out rows with unparseable dates
df_cleaned = df_cleaned.filter(col("date_entree_parsed").isNotNull())
print(f"✓ After date parsing: {df_cleaned.count()} rows")

# Validate Jour_Hospitalisation >= 0
df_cleaned = df_cleaned.filter(col("Jour_Hospitalisation") >= 0)
print(f"✓ After validating positive jour_hospitalisation: {df_cleaned.count()} rows")

# Add data quality flags
df_cleaned = df_cleaned.withColumn(
    "is_valid",
    when(
        (col("date_entree_parsed") >= to_date(lit("2015-01-01"))) &
        (col("date_entree_parsed") <= to_date(lit("2023-12-31"))),
        1
    ).otherwise(0)
)

print(f"✓ Valid rows (2015-2023): {df_cleaned.filter(col('is_valid') == 1).count()}")

# ============================================================================
# STAGE 7: GENERATE CLEANING REPORT
# ============================================================================

print("\n" + "=" * 80)
print("STAGE 7: CLEANING REPORT")
print("=" * 80)

report = {
    "timestamp": datetime.now().isoformat(),
    "rows_loaded": df_raw.count(),
    "rows_after_cleaning": df_cleaned.count(),
    "rows_removed": df_raw.count() - df_cleaned.count(),
    "removal_pct": ((df_raw.count() - df_cleaned.count()) / df_raw.count() * 100) if df_raw.count() > 0 else 0,
    "issues_found": len(issues),
    "issues": issues
}

print(f"\n📊 SUMMARY:")
print(f"  Input rows:        {report['rows_loaded']}")
print(f"  Output rows:       {report['rows_after_cleaning']}")
print(f"  Removed rows:      {report['rows_removed']} ({report['removal_pct']:.1f}%)")
print(f"  Issues found:      {report['issues_found']}")

if issues:
    print(f"\n⚠️  ISSUES TO RESOLVE:")
    for issue in issues:
        print(f"  {issue}")

# Save cleaned data
output_path = "data/staging/hospitalisations_cleaned"
df_cleaned.write.mode("overwrite").parquet(output_path)
print(f"\n✓ Cleaned data saved to: {output_path}")

# Save report
import json
report_path = f"reports/L2_profiling_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(report_path, 'w') as f:
    json.dump(report, f, indent=2)
print(f"✓ Report saved to: {report_path}")

print("\n" + "=" * 80)
print("✅ PROFILING, MAPPING & CLEANING COMPLETED")
print("=" * 80)
