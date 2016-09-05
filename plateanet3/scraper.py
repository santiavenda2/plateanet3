import signal
import asyncio
import aiohttp
import sys

from collections import defaultdict
from bs4 import BeautifulSoup
from pprint import pprint

PLATEANET_URL = "https://www.plateanet.com/"
PLATEANET_OBRA_URL = "https://www.plateanet.com/Obras/"
PLATEANET_GET_FUNCIONES_URL = "https://www.plateanet.com/Services/getFuncionesPorTeatroyObra"
PLATEANET_GET_SECTORES_Y_DESCUENTOS_URL = "https://www.plateanet.com/Services/getSectoresYDescuentos"


async def fetch_page(client, url):
    async with client.get(url) as response:
        assert response.status == 200
        return await response.read()


def get_obra_id(url):
    return url.rsplit("/", 1)[1]


async def get_obras_con_promocion(client):

    obras = await get_obras_en_cartel(client)
    total_obras = len(obras)
    for i, obra_id in enumerate(obras, start=1):
        print("processing obra: {} ({}/{})".format(obra_id, i, total_obras))
        obra_con_promociones = await get_promociones_obra(obra_id, client)
        pprint(obra_con_promociones)


async def get_obras_en_cartel(client):
    """
    Obtiene todas las obras con sus ids
    :param client:
    :return:
    """
    async with client.get(PLATEANET_URL) as response:
        assert response.status == 200
        html = await response.read()

    soup = BeautifulSoup(html, "html.parser")

    obras_options = soup.select("#Obras > option")
    obras = {}
    for obra in obras_options:
        url_obra = obra.get('value')
        if url_obra is not None:
            id_obra = get_obra_id(url_obra)
            nombre_obra = obra.text
            obras[id_obra] = (nombre_obra, url_obra)

    return obras


async def get_promociones_obra(nombre_obra, client):

    obra = {"nombre_obra": nombre_obra}
    print("Buscando info: {}".format(nombre_obra))
    id_teatro_w, id_obra_w = await get_info_obra(nombre_obra, client)
    obra["teatro"] = id_teatro_w
    obra["_id"] = id_obra_w

    print("Buscando funciones...")
    funciones = await get_funciones(id_teatro_w, id_obra_w, client)

    print("Buscando Sectores y descuentos")
    funciones_list = list()
    for id_funcion, nombre_funcion in funciones.items():
        funcion = {"_id": id_funcion, "nombre": nombre_funcion}
        promociones_encontradas = await get_sectores_y_descuentos(id_funcion, client)

        if promociones_encontradas:
            promos = list()
            for nombre_promo, sectores in promociones_encontradas.items():
                promo = {"nombre": nombre_promo, "sectores": sectores}
                promos.append(promo)
            funcion["promos"] = promos

        funciones_list.append(funcion)

    obra["funciones"] = funciones_list

    return obra


async def get_info_obra(name, client):
    """
    Usando el nombre (id_name) de la obra obtiene el id_obra y id_teatro
    """

    obra_url = PLATEANET_OBRA_URL + name
    async with client.get(obra_url) as response:
        assert response.status == 200
        html = await response.read()

    soup = BeautifulSoup(html, "html.parser")
    div_info_obra = soup.find(id="info")
    id_obra = div_info_obra.get("idobra")
    id_teatro = div_info_obra.get("idteatro")

    return id_teatro, id_obra


async def get_funciones(id_teatro, id_obra, client):
    """
    Usando id_teatro y id_obra obtiene los id_funciones de la obra

    var idTeatro=$('#drop1').val()
    idObra=$('#drop1 option:selected').attr('obraId')
    cantidadPedida=parseInt($('#dropEntr').val());
    $.post("/Services/getFuncionesPorTeatroyObra",{token:"..leofdfojerh.",nIdTeatro:idTeatro,nIdInfoObra:idObra}
    """

    params = {"token": "..leofdfojerh.", "nIdTeatro": id_teatro, "nIdInfoObra": id_obra}

    async with client.post(PLATEANET_GET_FUNCIONES_URL, data=params) as response:
        assert response.status == 200
        json_resp = await response.json()

    funciones = {}
    for funcion in json_resp["objeto"]['Funciones']:
        id_funcion = funcion["idFuncion"]
        nombre_funcion = funcion["Nombre"]
        funciones[id_funcion] = nombre_funcion
    return funciones


async def get_sectores_y_descuentos(id_funcion, client):
    """
    Usando el id de la obra obtiene los sectores y descuentos
    $.post("/Services/getSectoresYDescuentos",{token:"..leofdfojerh.",nIdFuncion:idFuncion}
    """
    params = {"token": "..leofdfojerh.", "nIdFuncion": id_funcion}
    async with client.post(PLATEANET_GET_SECTORES_Y_DESCUENTOS_URL, data=params) as response:
        assert response.status == 200
        json_resp = await response.json()

    promociones_encontradas = defaultdict(list)
    for sector in json_resp["objeto"]:
        totales = int(sector['Totales'])
        sector_disponible = int(sector['Disponible'])
        sector_nombre = sector['Sector']
        sector_precio = sector['Precio']
        promos_valida = [promo for promo in sector["Promos"] if promo["Nombre"] != "S/D"]
        for promo in promos_valida:
            nombre_promo = promo["Nombre"]
            vendidas = int(promo["Vendidas"])
            tope = int(promo["Quote"])
            disp_teorica = 0 if tope - vendidas < 0 else tope - vendidas
            disponibles = min(disp_teorica, sector_disponible)
            if disponibles > 0:
                promociones_encontradas[nombre_promo].append(sector_nombre)

    return promociones_encontradas


def run_loop():
    loop = asyncio.get_event_loop()
    client = aiohttp.ClientSession(loop=loop)

    def signal_handler(signal, frame):
        loop.stop()
        client.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    obras = loop.run_until_complete(get_obras_en_cartel(client))
    print(obras)

    tasks = [asyncio.ensure_future(get_promociones_obra(obra_id, client)) for obra_id in obras]
    loop.run_until_complete(asyncio.wait(tasks))

    client.close()
    print("Client closed")

if __name__ == '__main__':
    run_loop()
