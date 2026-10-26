import argparse
import csv
import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import psycopg2

TOTAL = 25
CARPETA = Path(__file__).resolve().parent

def conectar():
    conexion = psycopg2.connect(
        dbname=os.getenv("DB_NAME", "cines_imax"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "caca2"),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        connect_timeout=10,)
    with conexion.cursor() as cur:
        cur.execute("SET search_path TO public")
    return conexion

def revisar_asiento(cur, funcion, sala, asiento):
    cur.execute(
        "SELECT habilitado FROM asiento WHERE id_sala=%s AND numero=%s",
        (sala, asiento),)
    registro = cur.fetchone()
    if not registro or not registro[0]:
        return False, "asiento inexistente o deshabilitado"

    cur.execute(
        """SELECT 1 FROM entrada
           WHERE id_funcion=%s AND id_sala=%s AND numero_asiento=%s
             AND estado IN ('emitida','usada') LIMIT 1""",
        (funcion, sala, asiento),
    )
    if cur.fetchone():
        return False, "asiento vendido"
    cur.execute(
        """SELECT 1 FROM bloqueo_asiento
           WHERE id_funcion=%s AND id_sala=%s AND numero_asiento=%s
             AND estado='activo' AND vence_en>NOW() LIMIT 1""",
        (funcion, sala, asiento),
    )
    if cur.fetchone():
        return False, "asiento bloqueado"
    return True, "disponible"

def elegir_destino(conn, id_funcion=None, asiento_solicitado=None):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT f.id_funcion, f.id_sala, a.numero
               FROM funcion f
               JOIN asiento a ON a.id_sala=f.id_sala
               WHERE f.activa=TRUE AND f.fecha_hora>NOW()
                 AND a.habilitado=TRUE
                 AND (%s::bigint IS NULL OR f.id_funcion=%s::bigint)
                 AND (%s::varchar IS NULL OR a.numero=%s::varchar)
               ORDER BY f.fecha_hora, a.numero""",
            (id_funcion, id_funcion, asiento_solicitado, asiento_solicitado),)
        for funcion, sala, asiento in cur.fetchall():
            disponible, _ = revisar_asiento(cur, funcion, sala, asiento)
            if disponible:
                return funcion, sala, asiento
    raise ValueError(
        "No hay asientos libres en funciones futuras con esos filtros. "
        "Usa --funcion ID --asiento A1 o prepara una función de prueba.")

def crear_clientes_temporales(conn):
    inicio = 9_000_000_000_000 + secrets.randbelow(100_000_000) * 100
    ids = [inicio + numero for numero in range(TOTAL)]
    with conn.cursor() as cur:
        for n, cid in enumerate(ids, start=1):
            cur.execute(
                "INSERT INTO cliente(id_cliente,nombre,grupo_edad) VALUES (%s,%s,%s)",
                (cid, f"PRUEBA_CONCURRENCIA_{inicio}_{n:02}", "adulto"),
            )
    conn.commit()
    return ids

def intento(numero, id_cliente, id_funcion, id_sala, numero_asiento, barrera):
    inicio = time.perf_counter()
    conn = None
    bloqueo_creado = None
    try:
        conn = conectar()
        barrera.wait(timeout=30)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
                (f"imax:{id_funcion}:{id_sala}", numero_asiento),
            )
            disponible, razon = revisar_asiento(
                cur, id_funcion, id_sala, numero_asiento)
            if not disponible:
                conn.rollback()
                return {
                    "participante": numero, "id_cliente": id_cliente,
                    "resultado": "Rechazado", "detalle": razon,
                    "id_bloqueo": "", "duracion_ms": round((time.perf_counter()-inicio)*1000, 2),
                }
            cur.execute(
                """UPDATE bloqueo_asiento SET estado='expirado'
                   WHERE id_funcion=%s AND id_sala=%s AND numero_asiento=%s
                     AND estado='activo' AND vence_en<=NOW()""",
                (id_funcion, id_sala, numero_asiento),
            )
            cur.execute(
                """INSERT INTO bloqueo_asiento
                     (id_cliente,id_funcion,id_sala,numero_asiento)
                   VALUES (%s,%s,%s,%s) RETURNING id_bloqueo""",
                (id_cliente, id_funcion, id_sala, numero_asiento),
            )
            bloqueo_creado = cur.fetchone()[0]
            time.sleep(0.35)
        conn.commit()
        return {
            "participante": numero, "id_cliente": id_cliente,
            "resultado": "Aceptado", "detalle": "bloqueo temporal creado",
            "id_bloqueo": bloqueo_creado,
            "duracion_ms": round((time.perf_counter()-inicio)*1000, 2),
        }
    except Exception as exc:
        if conn:
            conn.rollback()
        return {
            "participante": numero, "id_cliente": id_cliente,
            "resultado": "Error", "detalle": f"{type(exc).__name__}: {exc}"[:250],
            "id_bloqueo": "", "duracion_ms": round((time.perf_counter()-inicio)*1000, 2),
        }
    finally:
        if conn:
            conn.close()

def limpiar(conn, ids_clientes, ids_bloqueos):
    with conn.cursor() as cur:
        if ids_bloqueos:
            cur.execute(
                "DELETE FROM bloqueo_asiento WHERE id_bloqueo = ANY(%s)",
                (ids_bloqueos,),
            )
        if ids_clientes:
            cur.execute(
                "DELETE FROM cliente WHERE id_cliente = ANY(%s)",
                (ids_clientes,),
            )
    conn.commit()

def main():
    parser = argparse.ArgumentParser(
        description="25 clientes compran el mismo asiento"
    )
    parser.add_argument("--funcion", type=int, help="ID de función; por defecto se elige una futura")
    parser.add_argument("--asiento", help="Asiento, p.ej. A1; por defecto se elige uno libre")
    parser.add_argument("--ejecutar", action="store_true", help="Autoriza crear y limpiar datos temporales")
    args = parser.parse_args()

    conn = None
    clientes = []
    ganadores = []
    resultados = []
    try:
        conn = conectar()
        funcion, sala, asiento = elegir_destino(conn, args.funcion, args.asiento)
        conn.commit()
        print(f"\nDestino: función {funcion} | sala {sala} | asiento {asiento}")
        print(f"Solicitudes simultáneas: {TOTAL}")
        if not args.ejecutar:
            print("MODO CONSULTA: no se escribió nada en PostgreSQL.")
            print("Para realizar la prueba en una BASE DE PRUEBAS, agrega --ejecutar.")
            return

        clientes = crear_clientes_temporales(conn)
        barrera = threading.Barrier(TOTAL)
        comienzo = time.perf_counter()
        with ThreadPoolExecutor(max_workers=TOTAL) as executor:
            futuros = [executor.submit(
                intento, i+1, clientes[i], funcion, sala, asiento, barrera
            ) for i in range(TOTAL)]
            for futuro in as_completed(futuros):
                resultados.append(futuro.result())
        tiempo_total = round((time.perf_counter()-comienzo)*1000, 2)
        resultados.sort(key=lambda r: r["participante"])
        ganadores = [r["id_bloqueo"] for r in resultados if r["resultado"] == "Aceptado"]
        aceptados = len(ganadores)
        rechazados = sum(r["resultado"] == "Rechazado" for r in resultados)
        errores = sum(r["resultado"] == "Error" for r in resultados)

        with conn.cursor() as cur:
            cur.execute(
                """SELECT count(*) FROM bloqueo_asiento
                   WHERE id_funcion=%s AND id_sala=%s AND numero_asiento=%s
                     AND estado='activo' AND vence_en>NOW()""",
                (funcion, sala, asiento),
            )
            bloqueos_activos = cur.fetchone()[0]
        conn.commit()

        sello = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta = CARPETA / f"resultado_concurrencia_25_{sello}.csv"
        with ruta.open("w", newline="", encoding="utf-8-sig") as archivo:
            escritor = csv.DictWriter(archivo, fieldnames=[
                "participante", "id_cliente", "resultado", "detalle", "id_bloqueo", "duracion_ms"
            ])
            escritor.writeheader()
            escritor.writerows(resultados)
        for r in resultados:
            print(f"{r['participante']:02d}. {r['resultado']:<9} {r['detalle']}")
        print("\nRESUMEN")
        print(f"Aceptados: {aceptados} | Rechazados: {rechazados} | Errores: {errores}")
        print(f"Bloqueos activos para el asiento al medir: {bloqueos_activos}")
        print(f"Duración conjunta: {tiempo_total} ms")
        print(f"CSV de evidencia: {ruta}")
        print("RESULTADO:", "aprobado" if (aceptados == 1 and rechazados == 24 and errores == 0 and bloqueos_activos == 1) else "REVISAR")
    except Exception as exc:
        print(f"ERROR GENERAL: {type(exc).__name__}: {exc}")
        raise
    finally:
        if conn:
            try:
                limpiar(conn, clientes, ganadores)
                if clientes:
                    print("Limpieza completada: se retiraron el bloqueo ganador y los 25 clientes temporales.")
            except Exception as exc:
                print("Atención: no se pudo limpiar automáticamente:", exc)
                print("Revisa solo las filas de prueba antes de repetir; no borres tablas completas.")
            finally:
                conn.close()

if __name__ == "__main__":
    main()