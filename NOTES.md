

# General Notes

## Installs
sudo apt update
sudo apt install python3.14-venv
sudo apt install sqlite3

## DB
The DB used is SQLite. Commands are a bit weird.

### In CLI
```
sqlite3 kollegianeren.db

```

### For a more readable print
```
.headers on
.mode column
```

### Check a table
---
Follows normal mySQL syntax
```
SELECT * FROM residents;
```

### Set ouput file
Use this command: **.output db_report.txt**
Now every query or command you make, will be written to that file.


