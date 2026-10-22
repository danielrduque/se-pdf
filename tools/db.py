"""Utilidades de la base de datos.

  python tools/db.py status   # esquemas, documentos y fragmentos
  python tools/db.py clean    # borra los esquemas temporales (d_*) que dejan las pruebas y qa_check
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chatpdf import store as st

if (problem := st.db_problem()):
    sys.exit(problem)
with st._pool().connection() as conn:
    schemas = [r[0] for r in conn.execute(r"SELECT nspname FROM pg_namespace WHERE nspname = 'chatdd' OR nspname LIKE 'd\_%' ORDER BY 1").fetchall()]
    if (sys.argv[1:] or ["status"])[0] == "clean":
        for s in schemas:
            if s != "chatdd":
                conn.execute(f"DROP SCHEMA {s} CASCADE")
        print(f"{len([s for s in schemas if s != 'chatdd'])} esquemas temporales borrados")
    else:
        for s in schemas:
            d, c, h, m = conn.execute(f"SELECT (SELECT count(*) FROM {s}.documents), (SELECT count(*) FROM {s}.chunks), (SELECT count(*) FROM {s}.chats), (SELECT count(*) FROM {s}.chat_messages)").fetchone()
            print(f"{s}: {d} documentos, {c} fragmentos, {h} chats, {m} mensajes")
