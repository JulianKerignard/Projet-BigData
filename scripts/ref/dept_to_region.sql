-- =============================================================
--  Table de référence : Département → Région
--  Découpage administratif : réforme territoriale du 1er janvier 2016
--  Source : Code officiel géographique (COG) INSEE
--
--  Périmètre : 96 départements métropolitains + 5 DOM + 7 COM/TOM
--  Total = 108 codes possibles
-- =============================================================

DROP TABLE IF EXISTS ref_dept_region;

CREATE TABLE ref_dept_region (
    code_departement VARCHAR(3) NOT NULL,    -- "01" .. "95", "2A", "2B", "971" .. "988"
    code_region      VARCHAR(2) NOT NULL,    -- code région INSEE
    nom_region       VARCHAR(64) NOT NULL,
    PRIMARY KEY (code_departement)
);

-- ---------------- Métropole (13 régions) ----------------

-- 11 - Île-de-France
INSERT INTO ref_dept_region VALUES ('75','11','Île-de-France');
INSERT INTO ref_dept_region VALUES ('77','11','Île-de-France');
INSERT INTO ref_dept_region VALUES ('78','11','Île-de-France');
INSERT INTO ref_dept_region VALUES ('91','11','Île-de-France');
INSERT INTO ref_dept_region VALUES ('92','11','Île-de-France');
INSERT INTO ref_dept_region VALUES ('93','11','Île-de-France');
INSERT INTO ref_dept_region VALUES ('94','11','Île-de-France');
INSERT INTO ref_dept_region VALUES ('95','11','Île-de-France');

-- 24 - Centre-Val de Loire
INSERT INTO ref_dept_region VALUES ('18','24','Centre-Val de Loire');
INSERT INTO ref_dept_region VALUES ('28','24','Centre-Val de Loire');
INSERT INTO ref_dept_region VALUES ('36','24','Centre-Val de Loire');
INSERT INTO ref_dept_region VALUES ('37','24','Centre-Val de Loire');
INSERT INTO ref_dept_region VALUES ('41','24','Centre-Val de Loire');
INSERT INTO ref_dept_region VALUES ('45','24','Centre-Val de Loire');

-- 27 - Bourgogne-Franche-Comté
INSERT INTO ref_dept_region VALUES ('21','27','Bourgogne-Franche-Comté');
INSERT INTO ref_dept_region VALUES ('25','27','Bourgogne-Franche-Comté');
INSERT INTO ref_dept_region VALUES ('39','27','Bourgogne-Franche-Comté');
INSERT INTO ref_dept_region VALUES ('58','27','Bourgogne-Franche-Comté');
INSERT INTO ref_dept_region VALUES ('70','27','Bourgogne-Franche-Comté');
INSERT INTO ref_dept_region VALUES ('71','27','Bourgogne-Franche-Comté');
INSERT INTO ref_dept_region VALUES ('89','27','Bourgogne-Franche-Comté');
INSERT INTO ref_dept_region VALUES ('90','27','Bourgogne-Franche-Comté');

-- 28 - Normandie
INSERT INTO ref_dept_region VALUES ('14','28','Normandie');
INSERT INTO ref_dept_region VALUES ('27','28','Normandie');
INSERT INTO ref_dept_region VALUES ('50','28','Normandie');
INSERT INTO ref_dept_region VALUES ('61','28','Normandie');
INSERT INTO ref_dept_region VALUES ('76','28','Normandie');

-- 32 - Hauts-de-France
INSERT INTO ref_dept_region VALUES ('02','32','Hauts-de-France');
INSERT INTO ref_dept_region VALUES ('59','32','Hauts-de-France');
INSERT INTO ref_dept_region VALUES ('60','32','Hauts-de-France');
INSERT INTO ref_dept_region VALUES ('62','32','Hauts-de-France');
INSERT INTO ref_dept_region VALUES ('80','32','Hauts-de-France');

-- 44 - Grand Est
INSERT INTO ref_dept_region VALUES ('08','44','Grand Est');
INSERT INTO ref_dept_region VALUES ('10','44','Grand Est');
INSERT INTO ref_dept_region VALUES ('51','44','Grand Est');
INSERT INTO ref_dept_region VALUES ('52','44','Grand Est');
INSERT INTO ref_dept_region VALUES ('54','44','Grand Est');
INSERT INTO ref_dept_region VALUES ('55','44','Grand Est');
INSERT INTO ref_dept_region VALUES ('57','44','Grand Est');
INSERT INTO ref_dept_region VALUES ('67','44','Grand Est');
INSERT INTO ref_dept_region VALUES ('68','44','Grand Est');
INSERT INTO ref_dept_region VALUES ('88','44','Grand Est');

-- 52 - Pays de la Loire
INSERT INTO ref_dept_region VALUES ('44','52','Pays de la Loire');
INSERT INTO ref_dept_region VALUES ('49','52','Pays de la Loire');
INSERT INTO ref_dept_region VALUES ('53','52','Pays de la Loire');
INSERT INTO ref_dept_region VALUES ('72','52','Pays de la Loire');
INSERT INTO ref_dept_region VALUES ('85','52','Pays de la Loire');

-- 53 - Bretagne
INSERT INTO ref_dept_region VALUES ('22','53','Bretagne');
INSERT INTO ref_dept_region VALUES ('29','53','Bretagne');
INSERT INTO ref_dept_region VALUES ('35','53','Bretagne');
INSERT INTO ref_dept_region VALUES ('56','53','Bretagne');

-- 75 - Nouvelle-Aquitaine
INSERT INTO ref_dept_region VALUES ('16','75','Nouvelle-Aquitaine');
INSERT INTO ref_dept_region VALUES ('17','75','Nouvelle-Aquitaine');
INSERT INTO ref_dept_region VALUES ('19','75','Nouvelle-Aquitaine');
INSERT INTO ref_dept_region VALUES ('23','75','Nouvelle-Aquitaine');
INSERT INTO ref_dept_region VALUES ('24','75','Nouvelle-Aquitaine');
INSERT INTO ref_dept_region VALUES ('33','75','Nouvelle-Aquitaine');
INSERT INTO ref_dept_region VALUES ('40','75','Nouvelle-Aquitaine');
INSERT INTO ref_dept_region VALUES ('47','75','Nouvelle-Aquitaine');
INSERT INTO ref_dept_region VALUES ('64','75','Nouvelle-Aquitaine');
INSERT INTO ref_dept_region VALUES ('79','75','Nouvelle-Aquitaine');
INSERT INTO ref_dept_region VALUES ('86','75','Nouvelle-Aquitaine');
INSERT INTO ref_dept_region VALUES ('87','75','Nouvelle-Aquitaine');

-- 76 - Occitanie
INSERT INTO ref_dept_region VALUES ('09','76','Occitanie');
INSERT INTO ref_dept_region VALUES ('11','76','Occitanie');
INSERT INTO ref_dept_region VALUES ('12','76','Occitanie');
INSERT INTO ref_dept_region VALUES ('30','76','Occitanie');
INSERT INTO ref_dept_region VALUES ('31','76','Occitanie');
INSERT INTO ref_dept_region VALUES ('32','76','Occitanie');
INSERT INTO ref_dept_region VALUES ('34','76','Occitanie');
INSERT INTO ref_dept_region VALUES ('46','76','Occitanie');
INSERT INTO ref_dept_region VALUES ('48','76','Occitanie');
INSERT INTO ref_dept_region VALUES ('65','76','Occitanie');
INSERT INTO ref_dept_region VALUES ('66','76','Occitanie');
INSERT INTO ref_dept_region VALUES ('81','76','Occitanie');
INSERT INTO ref_dept_region VALUES ('82','76','Occitanie');

-- 84 - Auvergne-Rhône-Alpes
INSERT INTO ref_dept_region VALUES ('01','84','Auvergne-Rhône-Alpes');
INSERT INTO ref_dept_region VALUES ('03','84','Auvergne-Rhône-Alpes');
INSERT INTO ref_dept_region VALUES ('07','84','Auvergne-Rhône-Alpes');
INSERT INTO ref_dept_region VALUES ('15','84','Auvergne-Rhône-Alpes');
INSERT INTO ref_dept_region VALUES ('26','84','Auvergne-Rhône-Alpes');
INSERT INTO ref_dept_region VALUES ('38','84','Auvergne-Rhône-Alpes');
INSERT INTO ref_dept_region VALUES ('42','84','Auvergne-Rhône-Alpes');
INSERT INTO ref_dept_region VALUES ('43','84','Auvergne-Rhône-Alpes');
INSERT INTO ref_dept_region VALUES ('63','84','Auvergne-Rhône-Alpes');
INSERT INTO ref_dept_region VALUES ('69','84','Auvergne-Rhône-Alpes');
INSERT INTO ref_dept_region VALUES ('73','84','Auvergne-Rhône-Alpes');
INSERT INTO ref_dept_region VALUES ('74','84','Auvergne-Rhône-Alpes');

-- 93 - Provence-Alpes-Côte d'Azur
INSERT INTO ref_dept_region VALUES ('04','93','Provence-Alpes-Côte d''Azur');
INSERT INTO ref_dept_region VALUES ('05','93','Provence-Alpes-Côte d''Azur');
INSERT INTO ref_dept_region VALUES ('06','93','Provence-Alpes-Côte d''Azur');
INSERT INTO ref_dept_region VALUES ('13','93','Provence-Alpes-Côte d''Azur');
INSERT INTO ref_dept_region VALUES ('83','93','Provence-Alpes-Côte d''Azur');
INSERT INTO ref_dept_region VALUES ('84','93','Provence-Alpes-Côte d''Azur');

-- 94 - Corse (codes spéciaux 2A / 2B)
INSERT INTO ref_dept_region VALUES ('2A','94','Corse');
INSERT INTO ref_dept_region VALUES ('2B','94','Corse');

-- ---------------- Départements et collectivités d'outre-mer ----------------

-- DOM
INSERT INTO ref_dept_region VALUES ('971','01','Guadeloupe');
INSERT INTO ref_dept_region VALUES ('972','02','Martinique');
INSERT INTO ref_dept_region VALUES ('973','03','Guyane');
INSERT INTO ref_dept_region VALUES ('974','04','La Réunion');
INSERT INTO ref_dept_region VALUES ('976','06','Mayotte');

-- COM / TOM
INSERT INTO ref_dept_region VALUES ('975','00','Saint-Pierre-et-Miquelon');
INSERT INTO ref_dept_region VALUES ('977','00','Saint-Barthélemy');
INSERT INTO ref_dept_region VALUES ('978','00','Saint-Martin');
INSERT INTO ref_dept_region VALUES ('984','00','Terres australes et antarctiques');
INSERT INTO ref_dept_region VALUES ('986','00','Wallis-et-Futuna');
INSERT INTO ref_dept_region VALUES ('987','00','Polynésie française');
INSERT INTO ref_dept_region VALUES ('988','00','Nouvelle-Calédonie');

-- =============================================================
--  Vérification
-- =============================================================
-- SELECT COUNT(*) FROM ref_dept_region;       -- attendu : 108
-- SELECT code_region, nom_region, COUNT(*) FROM ref_dept_region GROUP BY code_region, nom_region ORDER BY code_region;
