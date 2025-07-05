# connection_check.py  ── ya isi block ko main.py ke upar paste kar do
from neo4j import GraphDatabase
from settings import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

def check_neo4j_connection() -> None:
    """
    Console par ✓ / ✗ print kare-ga so you instantly know the status.
    Works for both auth-enabled and auth-disabled setups.
    """
    # Auth disabled ho to NEO4J_USER ko "" ya None set karo aur auth=None bhejo
    auth_tuple = None if not NEO4J_USER else (NEO4J_USER, NEO4J_PASSWORD)

    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=auth_tuple)
        # Driver-v5 ka builtin ping
        driver.verify_connectivity()                # yahan fail hua to except me chala jaayega

        # Extra sanity query
        with driver.session() as s:
            ok = s.run("RETURN 1 AS ok").single()["ok"]
        print(f"✅  Neo4j connected (RETURN 1 ⇒ {ok})")

    except Exception as e:
        print("❌  Neo4j connection failed →", e)

    finally:
        try:
            driver.close()
        except Exception:
            pass
