"""Medición 1: 20 descargas locales secuenciales y concurrentes."""

import asyncio
import json
import time

import httpx


CANTIDAD = 20
DEMORA = 0.1


async def responder(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        await reader.readuntil(b"\r\n\r\n")
        await asyncio.sleep(DEMORA)
        cuerpo = b"contenido de prueba"
        writer.write(
            b"HTTP/1.1 200 OK\r\n"
            + f"Content-Length: {len(cuerpo)}\r\n".encode()
            + b"Connection: close\r\n\r\n"
            + cuerpo
        )
        await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()


async def medir():
    servidor = await asyncio.start_server(responder, "127.0.0.1", 0)
    puerto = servidor.sockets[0].getsockname()[1]
    urls = [f"http://127.0.0.1:{puerto}/archivo/{n}" for n in range(CANTIDAD)]

    async with servidor, httpx.AsyncClient(timeout=5) as cliente:
        inicio = time.perf_counter()
        for url in urls:
            await cliente.get(url)
        secuencial = time.perf_counter() - inicio

        inicio = time.perf_counter()
        await asyncio.gather(*(cliente.get(url) for url in urls))
        concurrente = time.perf_counter() - inicio

    return {
        "cantidad": CANTIDAD,
        "demora_servidor_por_respuesta": DEMORA,
        "tiempo_secuencial": secuencial,
        "tiempo_concurrente": concurrente,
        "speedup": secuencial / concurrente,
        "condicion": "servidor HTTP local con 100 ms por respuesta",
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(medir()), indent=2))

