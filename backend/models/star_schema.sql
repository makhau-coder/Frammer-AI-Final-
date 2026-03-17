DROP TABLE IF EXISTS fact_video;

DROP TABLE IF EXISTS dim_user;
DROP TABLE IF EXISTS dim_team;
DROP TABLE IF EXISTS dim_input_type;
DROP TABLE IF EXISTS dim_platform;
DROP TABLE IF EXISTS dim_date;

DROP TABLE IF EXISTS agg_monthly_metrics;
DROP TABLE IF EXISTS agg_platform_metrics;
DROP TABLE IF EXISTS agg_channel_user;


CREATE TABLE dim_user(
user_id INTEGER PRIMARY KEY,
user_name VARCHAR,
is_qa_account BOOLEAN
);

CREATE TABLE dim_team(
team_id INTEGER PRIMARY KEY,
team_name VARCHAR
);

CREATE TABLE dim_input_type(
input_type_id INTEGER PRIMARY KEY,
input_type_name VARCHAR
);

CREATE TABLE dim_platform(
platform_id INTEGER PRIMARY KEY,
platform_name VARCHAR
);

CREATE TABLE dim_date(
date_id INTEGER PRIMARY KEY,
month VARCHAR,
year INTEGER,
month_number INTEGER,
quarter INTEGER
);


CREATE TABLE fact_video (
    video_id VARCHAR,
    headline VARCHAR,
    user_id INTEGER,
    input_type_id INTEGER,
    platform_id INTEGER,
    team_id INTEGER,
    date_id INTEGER,
    uploaded_count INTEGER,
    created_count INTEGER,
    published_count INTEGER,
    uploaded_mins DOUBLE,
    created_mins DOUBLE,
    published_mins DOUBLE,
    is_published BOOLEAN,
    published_url TEXT,
    publish_rate        FLOAT,          -- published / created * 100
    multiplication_ratio FLOAT,         -- created / uploaded
    unpublished_gap     INTEGER         -- created - published
);


CREATE TABLE agg_monthly_metrics(

month VARCHAR,

uploaded_count INTEGER,
created_count INTEGER,
published_count INTEGER,

uploaded_duration FLOAT,
created_duration FLOAT,
published_duration FLOAT
);


CREATE TABLE agg_platform_metrics(

channel VARCHAR,
platform VARCHAR,

publish_count INTEGER,
publish_duration FLOAT
);


CREATE TABLE agg_channel_user(

channel VARCHAR,
user_name VARCHAR,

uploaded_count INTEGER,
created_count INTEGER,
published_count INTEGER,

uploaded_duration FLOAT,
created_duration FLOAT,
published_duration FLOAT
);