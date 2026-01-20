--------------------------------------------------------------
--
-- PostgreSQL database dump
--

-- Dumped from database version 11.7
-- Dumped by pg_dump version 17.0

-- Started on 2025-04-08 12:12:29 NZST
--------------------------------------------------------------

SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

--------------------------------------------------------------

CREATE TABLE public.alternative_terms (
    source_id character varying NOT NULL,
    term_id character varying NOT NULL,
    alternative_id character varying NOT NULL
);
ALTER TABLE public.alternative_terms OWNER TO abi;

CREATE TABLE public.anatomical_types (
    type_id character varying NOT NULL,
    label text NOT NULL,
    description text
);
ALTER TABLE public.anatomical_types OWNER TO abi;

CREATE TABLE public.path_node_features (
    source_id character varying NOT NULL,
    path_id character varying NOT NULL,
    node_id character varying NOT NULL,
    feature_id character varying NOT NULL
);
ALTER TABLE public.path_node_features OWNER TO abi;

CREATE TABLE public.path_node_types (
    source_id character varying NOT NULL,
    path_id character varying NOT NULL,
    node_id character varying NOT NULL,
    type_id character varying NOT NULL
);
ALTER TABLE public.path_node_types OWNER TO abi;

CREATE TABLE public.path_nodes (
    source_id character varying NOT NULL,
    path_id character varying NOT NULL,
    node_id character varying NOT NULL,
    label text
);
ALTER TABLE public.path_nodes OWNER TO abi;

CREATE TABLE public.path_edges (
    source_id character varying NOT NULL,
    path_id character varying NOT NULL,
    node_0 character varying NOT NULL,
    node_1 character varying NOT NULL
);
ALTER TABLE public.path_edges OWNER TO abi;

CREATE TABLE public.path_features (
    source_id character varying NOT NULL,
    path_id character varying NOT NULL,
    feature_id character varying NOT NULL
);
ALTER TABLE public.path_features OWNER TO abi;

CREATE TABLE public.path_forward_connections (
    source_id character varying NOT NULL,
    path_id character varying NOT NULL,
    forward_path_id character varying NOT NULL
);
ALTER TABLE public.path_forward_connections OWNER TO abi;

CREATE TABLE public.path_phenotypes (
    source_id character varying NOT NULL,
    path_id character varying NOT NULL,
    phenotype character varying NOT NULL
);
ALTER TABLE public.path_phenotypes OWNER TO abi;

CREATE TABLE public.path_properties (
    source_id character varying NOT NULL,
    path_id character varying NOT NULL,
    biological_sex character varying,
    alert text,
    disconnected boolean DEFAULT false NOT NULL
);
ALTER TABLE public.path_properties OWNER TO abi;

CREATE TABLE public.path_taxons (
    source_id character varying NOT NULL,
    path_id character varying NOT NULL,
    taxon_id character varying NOT NULL
);
ALTER TABLE public.path_taxons OWNER TO abi;

CREATE TABLE public.evidence (
    evidence_id character varying NOT NULL,
    type character varying,
    details text
);
ALTER TABLE public.evidence OWNER TO abi;

CREATE TABLE public.feature_evidence (
    source_id character varying NOT NULL,
    term_id character varying NOT NULL,
    evidence_id character varying NOT NULL
);
ALTER TABLE public.feature_evidence OWNER TO abi;

CREATE TABLE public.feature_relationship (  -- this could be used for forward connections
    source_id character varying NOT NULL,
    feature_0 character varying NOT NULL,
    feature_1 character varying NOT NULL,
    relationship character varying NOT NULL
);
ALTER TABLE public.feature_relationship OWNER TO abi;

CREATE TABLE public.feature_terms (
    source_id character varying NOT NULL,
    term_id character varying NOT NULL,
    label text,
    description text
);
ALTER TABLE public.feature_terms OWNER TO abi;

CREATE TABLE public.feature_types (
    source_id character varying NOT NULL,
    term_id character varying NOT NULL,
    type_id character varying NOT NULL
);
ALTER TABLE public.feature_types OWNER TO abi;

CREATE TABLE public.knowledge_sources (
    source_id character varying NOT NULL,
    sckan_id character varying NOT NULL,
    description text
);
ALTER TABLE public.knowledge_sources OWNER TO abi;

CREATE TABLE public.taxons (
    taxon_id character varying NOT NULL,
    description text
);
ALTER TABLE public.taxons OWNER TO abi;

CREATE TABLE public.path_node_mappings (
    source_id character varying NOT NULL,
    path_id character varying NOT NULL,
    node_id character varying NOT NULL,
    sckan_id character varying,
    sckan_node_id character varying
);
ALTER TABLE public.path_node_mappings OWNER TO abi;

--------------------------------------------------------------

ALTER TABLE ONLY public.anatomical_types
    ADD CONSTRAINT anatomical_types_pkey PRIMARY KEY (type_id);

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT evidence_pkey PRIMARY KEY (evidence_id);

ALTER TABLE ONLY public.knowledge_sources
    ADD CONSTRAINT knowledge_sources_pkey PRIMARY KEY (source_id);

ALTER TABLE ONLY public.taxons
    ADD CONSTRAINT taxons_pkey PRIMARY KEY (taxon_id);

--------------------------------------------------------------

CREATE INDEX fki_node_0_constraint ON public.path_edges USING btree (node_0);
CREATE INDEX fki_node_1_constraint ON public.path_edges USING btree (node_1);
CREATE INDEX fki_path_node_0_constraint ON public.path_edges USING btree (path_id, node_0);
CREATE INDEX fki_path_node_1_constraint ON public.path_edges USING btree (path_id, node_1);

CREATE INDEX fki_path_constraint ON public.path_properties USING btree (path_id);

CREATE INDEX fki_node_constraint ON public.path_node_types USING btree (node_id);
CREATE INDEX fki_path_node_constraint ON public.path_node_types USING btree (node_id, path_id);

--------------------------------------------------------------

ALTER TABLE IF EXISTS public.path_nodes
    ADD CONSTRAINT source_node_constraint UNIQUE (source_id, path_id, node_id);

ALTER TABLE IF EXISTS public.feature_terms
    ADD CONSTRAINT source_term_constraint UNIQUE (source_id, term_id);

--------------------------------------------------------------

ALTER TABLE ONLY public.alternative_terms
    ADD CONSTRAINT source_constraint FOREIGN KEY (source_id) REFERENCES public.knowledge_sources(source_id);
ALTER TABLE ONLY public.alternative_terms
    ADD CONSTRAINT term_constraint FOREIGN KEY (source_id, term_id) REFERENCES public.feature_terms(source_id, term_id);
ALTER TABLE ONLY public.alternative_terms
    ADD CONSTRAINT alternative_constraint FOREIGN KEY (source_id, alternative_id) REFERENCES public.feature_terms(source_id, term_id);

ALTER TABLE ONLY public.path_node_features
    ADD CONSTRAINT source_constraint FOREIGN KEY (source_id) REFERENCES public.knowledge_sources(source_id);
ALTER TABLE ONLY public.path_node_features
    ADD CONSTRAINT path_constraint FOREIGN KEY (source_id, path_id) REFERENCES public.feature_terms(source_id, term_id);
ALTER TABLE ONLY public.path_node_features
    ADD CONSTRAINT node_constraint FOREIGN KEY (source_id, path_id, node_id) REFERENCES public.path_nodes(source_id, path_id, node_id);
ALTER TABLE ONLY public.path_node_features
    ADD CONSTRAINT feature_constraint FOREIGN KEY (source_id, feature_id) REFERENCES public.feature_terms(source_id, term_id);

ALTER TABLE ONLY public.path_node_types
    ADD CONSTRAINT source_constraint FOREIGN KEY (source_id) REFERENCES public.knowledge_sources(source_id);
ALTER TABLE ONLY public.path_node_types
    ADD CONSTRAINT path_constraint FOREIGN KEY (source_id, path_id) REFERENCES public.feature_terms(source_id, term_id);
ALTER TABLE ONLY public.path_node_types
    ADD CONSTRAINT node_constraint FOREIGN KEY (source_id, path_id, node_id) REFERENCES public.path_nodes(source_id, path_id, node_id);
ALTER TABLE ONLY public.path_node_types
    ADD CONSTRAINT type_constraint FOREIGN KEY (type_id) REFERENCES public.anatomical_types(type_id);

ALTER TABLE ONLY public.path_nodes
    ADD CONSTRAINT source_constraint FOREIGN KEY (source_id) REFERENCES public.knowledge_sources(source_id);
ALTER TABLE ONLY public.path_nodes
    ADD CONSTRAINT path_constraint FOREIGN KEY (source_id, path_id) REFERENCES public.feature_terms(source_id, term_id);

ALTER TABLE ONLY public.path_edges
    ADD CONSTRAINT source_constraint FOREIGN KEY (source_id) REFERENCES public.knowledge_sources(source_id);
ALTER TABLE ONLY public.path_edges
    ADD CONSTRAINT path_constraint FOREIGN KEY (source_id, path_id) REFERENCES public.feature_terms(source_id, term_id);
ALTER TABLE ONLY public.path_edges
    ADD CONSTRAINT node_0_constraint FOREIGN KEY (source_id, path_id, node_0) REFERENCES public.path_nodes(source_id, path_id, node_id);
ALTER TABLE ONLY public.path_edges
    ADD CONSTRAINT node_1_constraint FOREIGN KEY (source_id, path_id, node_1) REFERENCES public.path_nodes(source_id, path_id, node_id);

ALTER TABLE ONLY public.path_features
    ADD CONSTRAINT source_constraint FOREIGN KEY (source_id) REFERENCES public.knowledge_sources(source_id);
ALTER TABLE ONLY public.path_features
    ADD CONSTRAINT path_constraint FOREIGN KEY (source_id, path_id) REFERENCES public.feature_terms(source_id, term_id);
ALTER TABLE ONLY public.path_features
    ADD CONSTRAINT feature_constraint FOREIGN KEY (source_id, feature_id) REFERENCES public.feature_terms(source_id, term_id);

ALTER TABLE ONLY public.path_forward_connections
    ADD CONSTRAINT source_constraint FOREIGN KEY (source_id) REFERENCES public.knowledge_sources(source_id);
ALTER TABLE ONLY public.path_forward_connections
    ADD CONSTRAINT path_constraint FOREIGN KEY (source_id, path_id) REFERENCES public.feature_terms(source_id, term_id);
ALTER TABLE ONLY public.path_forward_connections
    ADD CONSTRAINT forward_path_constraint FOREIGN KEY (source_id, forward_path_id) REFERENCES public.feature_terms(source_id, term_id);

ALTER TABLE ONLY public.path_phenotypes
    ADD CONSTRAINT source_constraint FOREIGN KEY (source_id) REFERENCES public.knowledge_sources(source_id);
ALTER TABLE ONLY public.path_phenotypes
    ADD CONSTRAINT path_constraint FOREIGN KEY (source_id, path_id) REFERENCES public.feature_terms(source_id, term_id);

ALTER TABLE ONLY public.path_properties
    ADD CONSTRAINT source_constraint FOREIGN KEY (source_id) REFERENCES public.knowledge_sources(source_id);
ALTER TABLE ONLY public.path_properties
    ADD CONSTRAINT path_constraint FOREIGN KEY (source_id, path_id) REFERENCES public.feature_terms(source_id, term_id);

ALTER TABLE ONLY public.path_taxons
    ADD CONSTRAINT source_constraint FOREIGN KEY (source_id) REFERENCES public.knowledge_sources(source_id);
ALTER TABLE ONLY public.path_taxons
    ADD CONSTRAINT path_constraint FOREIGN KEY (source_id, path_id) REFERENCES public.feature_terms(source_id, term_id);
ALTER TABLE ONLY public.path_taxons
    ADD CONSTRAINT taxon_constraint FOREIGN KEY (taxon_id) REFERENCES public.taxons(taxon_id);

ALTER TABLE ONLY public.feature_evidence
    ADD CONSTRAINT source_constraint FOREIGN KEY (source_id) REFERENCES public.knowledge_sources(source_id);
ALTER TABLE ONLY public.feature_evidence
    ADD CONSTRAINT feature_constraint FOREIGN KEY (source_id, term_id) REFERENCES public.feature_terms(source_id, term_id);
ALTER TABLE ONLY public.feature_evidence
    ADD CONSTRAINT evidence_constraint FOREIGN KEY (evidence_id) REFERENCES public.evidence(evidence_id);

ALTER TABLE ONLY public.feature_relationship
    ADD CONSTRAINT source_constraint FOREIGN KEY (source_id) REFERENCES public.knowledge_sources(source_id);
ALTER TABLE ONLY public.feature_relationship
    ADD CONSTRAINT feature_0_constraint FOREIGN KEY (source_id, feature_0) REFERENCES public.feature_terms(source_id, term_id);
ALTER TABLE ONLY public.feature_relationship
    ADD CONSTRAINT feature_1_constraint FOREIGN KEY (source_id, feature_1) REFERENCES public.feature_terms(source_id, term_id);

ALTER TABLE ONLY public.feature_terms
    ADD CONSTRAINT source_constraint FOREIGN KEY (source_id) REFERENCES public.knowledge_sources(source_id);

ALTER TABLE ONLY public.feature_types
    ADD CONSTRAINT source_constraint FOREIGN KEY (source_id) REFERENCES public.knowledge_sources(source_id);
ALTER TABLE ONLY public.feature_types
    ADD CONSTRAINT feature_constraint FOREIGN KEY (source_id, term_id) REFERENCES public.feature_terms(source_id, term_id);
ALTER TABLE ONLY public.feature_types
    ADD CONSTRAINT type_constraint FOREIGN KEY (type_id) REFERENCES public.anatomical_types(type_id);

ALTER TABLE ONLY public.path_node_mappings
    ADD CONSTRAINT source_constraint FOREIGN KEY (source_id) REFERENCES public.knowledge_sources(source_id);
ALTER TABLE ONLY public.path_node_mappings
    ADD CONSTRAINT path_constraint FOREIGN KEY (source_id, path_id) REFERENCES public.feature_terms(source_id, term_id);
ALTER TABLE ONLY public.path_node_mappings
    ADD CONSTRAINT node_constraint FOREIGN KEY (source_id, path_id, node_id) REFERENCES public.path_nodes(source_id, path_id, node_id);
ALTER TABLE ONLY public.path_node_mappings
    ADD CONSTRAINT sckan_constraint FOREIGN KEY (sckan_id) REFERENCES public.knowledge_sources(source_id);
ALTER TABLE ONLY public.path_node_mappings
    ADD CONSTRAINT sckan_path_constraint FOREIGN KEY (sckan_id, path_id) REFERENCES public.feature_terms(source_id, term_id);
ALTER TABLE ONLY public.path_node_mappings
    ADD CONSTRAINT sckan_node_constraint FOREIGN KEY (sckan_id, path_id, node_id) REFERENCES public.path_nodes(source_id, path_id, node_id);

--------------------------------------------------------------
