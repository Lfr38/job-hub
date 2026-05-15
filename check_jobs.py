from execution.db_client import _get_connection

conn = _get_connection()
cursor = conn.cursor()

cursor.execute('SELECT COUNT(*) FROM jobs WHERE status = "filtered_pass" AND title LIKE "%Senior%"')
print(f'Senior jobs in filtered_pass: {cursor.fetchone()[0]}')

cursor.execute('SELECT COUNT(*) FROM jobs WHERE status = "filtered_pass"')
print(f'Total filtered_pass: {cursor.fetchone()[0]}')

print("\nTop 10 filtered_pass by score:")
cursor.execute('SELECT title, company, heuristic_score FROM jobs WHERE status = "filtered_pass" ORDER BY heuristic_score DESC LIMIT 10')
for r in cursor.fetchall():
    print(f'  score={r["heuristic_score"]:>3} | {r["title"][:55]:<55} | {r["company"][:30]}')

conn.close()
