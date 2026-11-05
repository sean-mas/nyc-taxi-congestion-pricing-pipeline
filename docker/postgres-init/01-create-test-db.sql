-- Runs once, when the Postgres volume is first created.
-- Integration tests use this separate database so they never touch real data.
CREATE DATABASE green_taxi_test;
