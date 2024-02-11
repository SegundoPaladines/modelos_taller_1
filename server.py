import socket
import multiprocessing
import os
from multiprocessing import Lock
from user import User
import time

# configuracion
host = "127.0.0.1"
port = 5000

# crear el socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# enalzer direccion ip y puerto
server_socket.bind((host, port))

print("Escuchando por el puerto 5000...")

# variables compartidas
manager = multiprocessing.Manager()
clientes = manager.list([User("Segundo","123","127.0.0.1", 5001)])
ocupados = manager.list([5000, 5001])
oferta = manager.dict({"user": None, "valor": 5000})
temporizador_proceso = None
temporizador_estado = None

lock_oferta = Lock()

#manejo del tiempo
estado_global = manager.Namespace()
estado_global.temporizador_proceso = None
estado_global.temporizador_estado = manager.dict({'tiempo': 0})

cola_de_comunicacion = multiprocessing.Queue()

def escucharPuerto(puerto, client_add, cola, clientes, ocupados):
    sv_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sv_socket.bind((host, puerto))

    cliente = None
    sesion = False

    while True:
        try:
            nuevos_clientes, nuevos_ocupados = cola.get_nowait()
            clientes[:] = nuevos_clientes
            ocupados[:] = nuevos_ocupados
        except Exception:
            pass

        # Pedir usuario
        response = f"Ingrese su usuario: {puerto}"
        sv_socket.sendto(response.encode("utf-8"), client_add)
        data, client_add = sv_socket.recvfrom(1024)

        usr = data.decode("utf-8")

        existe = False
        contador = 0
        for usuario in clientes:
            if usr == usuario.nombre:
                cliente = usuario
                existe = True
                break
            
        if existe:
            nuevos_clientes = [u for u in clientes if u.nombre != cliente.nombre]
            clientes[:] = nuevos_clientes
            
            # pedir contraseña
            response = f"Contraseña para {cliente.nombre}"
            sv_socket.sendto(response.encode("utf-8"), client_add)
            data, client_add = sv_socket.recvfrom(1024)

            if data.decode("utf-8") == cliente.password:
                sesion = True
            else:
                contador = 1
                while cliente.password != data.decode("utf-8") and contador < 3:
                    # pedir contraseña
                    response = f"Contraseña incorrecta, intente denuevo"
                    sv_socket.sendto(response.encode("utf-8"), client_add)
                    data, client_add = sv_socket.recvfrom(1024)

                    if data.decode("utf-8") == cliente.password:
                        sesion = True
                        break

                    contador += 1

                if contador >= 3:
                    response = f"Demasiados intentos con contraseña incorrecta"
                    sv_socket.sendto(response.encode("utf-8"), client_add)
                    break

            if sesion:
                # Si se logeó
                response = f"""
                Logeado con éxito, Bienvenido denuevo {cliente.nombre}
                Listado de comandos:
                ls ver subasta
                o <valor> hacer oferta
                q <- salir
                """
                sv_socket.sendto(response.encode("utf-8"), client_add)
                cliente.address = client_add[0]
                cliente.port = puerto

                clientes.append(cliente)
            break

        else:
            response = f"El usuario no existe, ¿desea crear uno Nuevo [Y/n]?"
            sv_socket.sendto(response.encode("utf-8"), client_add)
            data, client_add = sv_socket.recvfrom(1024)

            if data.decode("utf-8").lower() == "y":
                response = f"Ingrese la nueva Contraseña"
                sv_socket.sendto(response.encode("utf-8"), client_add)
                data, client_add = sv_socket.recvfrom(1024)

                cliente = User(usr, data.decode("utf-8"), client_add[0], puerto)
                clientes.append(cliente)

                response = f"""
                Logeado con éxito, Bienvenido {cliente.nombre}
                Listado de comandos:
                ls <- ver subasta
                o <valor> <- hacer oferta
                h <- ayuda
                q <- salir
                """
                sv_socket.sendto(response.encode("utf-8"), client_add)

                sesion = True

                ocupados.append(puerto)

            break

    cola.put((clientes, ocupados))

    while sesion:
        try:
            nuevos_clientes, nuevos_ocupados = cola.get_nowait()
            clientes[:] = nuevos_clientes
            ocupados[:] = nuevos_ocupados
        except Exception:
            pass

        data, client_add = sv_socket.recvfrom(1024)

        # manejo del cliente
        print(f"Cliente ({client_add[0]}:{client_add[1]}): {data}")

        comando = data.decode("utf-8")

        if comando.lower() == "q":
            response = f"""{puerto}@{cliente.nombre}
            Hasta la próxima...
            """
            sv_socket.sendto(response.encode("utf-8"), client_add)
            
            break
        elif comando == "h":
            response = f"""{puerto}@{cliente.nombre}
                Listado de comandos:
                ls <- ver subasta
                o <valor> <- hacer oferta
                h <- ayuda
                q <- salir
                """
        elif comando == "ls":
            if oferta is None:
                response = f"{puerto}@{cliente.nombre}: La puja comienza en $5000"
            else:
                # imprimir oferta
                if(10 - estado_global.temporizador_estado['tiempo']>0):
                    response = f"{puerto}@{cliente.nombre}: Mejor oferta: ${oferta['valor']} Tiempo restante para ofertar: {10 - estado_global.temporizador_estado['tiempo']}"
                else:
                    response = f"{puerto}@{cliente.nombre}: El tiempo se terminó - Ganador: {oferta['user']} <- ${oferta['valor']}"
                    
        elif comando.startswith("o "):
            client = None
            for c in clientes:
                if c.nombre == usr:
                    client = c
                    
            if client is not None:
                response = recibirOferta(int(comando.split()[1]), client, sv_socket, clientes, cola)
            else:
                response = f"Error al recibir oferta {int(comando.split()[1])}" 
        else:
            response = f"{puerto}@{cliente.nombre}"

        sv_socket.sendto(response.encode("utf-8"), client_add)
            

    sv_socket.close()
    ocupados.remove(puerto)
    cola.put((clientes, ocupados))
    os._exit(0)
    
def recibirOferta(valor, cliente, sv_socket, clientes, cola):
    global oferta, lock_oferta
    lock_oferta.acquire()
    try:
        inicializarTemporizador(estado_global, cliente, clientes, sv_socket)
        
        if(10 - estado_global.temporizador_estado['tiempo'] > 0):
            if oferta["valor"] == 0 or valor > oferta["valor"]:
                oferta["user"] = cliente.nombre
                oferta["valor"] = valor
                msg = f"La oferta subió a ${valor}:"
                try:
                    nuevos_clientes, nuevos_ocupados = cola.get_nowait()
                    clientes[:] = nuevos_clientes
                    ocupados[:] = nuevos_ocupados
                except Exception:
                    pass
                
                estado_global.temporizador_estado['tiempo'] = 0
                 
                for ur in clientes:
                    try:
                        p = ur.port+50
                        print(p)
                        sv_socket.sendto(msg.encode("utf-8"), (ur.address, p))
                    except Exception as e:
                        print(f"Error al enviar notificación de oferta a {ur.nombre}: {e}")
            
            return ""
        else:
            return f"La subasta ya finalizo: Ganador: {oferta['user']} <- ${oferta['valor']}"
    finally:
        lock_oferta.release()
        
def asignarPuerto(client_add):
    libre = 0
    for i in range(5000, 5050):
        if i not in ocupados:
            libre = i
            ocupados.append(libre)
            break

    if libre != 0:
        response = str(libre)
        server_socket.sendto(response.encode("utf-8"), client_add)
        proceso = multiprocessing.Process(target=escucharPuerto, args=(libre, client_add, cola_de_comunicacion, clientes, ocupados))
        proceso.start()

    else:
        response = "5000"
        server_socket.sendto(response.encode("utf-8"), client_add)

def contarTiempo(temporizador, cliente, clientes, sv_socket):
    temporizador['tiempo'] = 0
    while temporizador['tiempo'] < 10:
        time.sleep(1)
        temporizador['tiempo'] += 1
        print(f"Tiempo actual: {temporizador['tiempo']}")
    
    for ur in clientes:
        if cliente.nombre == ur.nombre:
            try:
                msg = "Felicidades, ha ganado la subasta!"
                p = ur.port+50
                print(p)
                sv_socket.sendto(msg.encode("utf-8"), (ur.address, p))
            except Exception as e:
                print(f"No se pudo notifiacar al ganador {e}")
            
            break

    print("Finalizó el tiempo")

def inicializarTemporizador(estado_global, cliente, clientes, sv_socket):
    if estado_global.temporizador_proceso is None or not estado_global.temporizador_proceso:
        temporizador = estado_global.temporizador_estado
        proceso = multiprocessing.Process(target=contarTiempo, args=(temporizador, cliente, clientes, sv_socket,))
        proceso.start()
        estado_global.temporizador_proceso = True
        print("Temporizador iniciado.")
    else:
        print("El temporizador ya está en ejecución.")
    
while True:
    data, client_add = server_socket.recvfrom(1024)
    message = data.decode("utf-8")
    print(f"Cliente ({client_add[0]}:{client_add[1]}): Iniciando Sesión...")
    asignarPuerto(client_add)
    