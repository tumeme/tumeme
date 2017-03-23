#!/usr/bin/env python
from db_wrapper import Database
import config 

if __name__ == "__main__":
    print("delet dis")
    Database.apply_query(config.DB_PATH, "DELETE FROM img")
    Database.apply_query(config.DB_PATH, "DELETE FROM queue")
    Database.apply_query(config.DB_PATH, "DELETE FROM kackchas")
    Database.apply_query(config.DB_PATH, "DELETE FROM cookiejar")


