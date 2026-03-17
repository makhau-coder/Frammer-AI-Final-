import duckdb

con = duckdb.connect("frammer_analytics.duckdb")
print(con.execute("SHOW TABLES").fetchall())

print(con.execute("DESCRIBE fact_video").fetchall())