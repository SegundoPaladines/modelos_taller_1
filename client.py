import socket
import threading
import queue  # Importar el módulo queue

host = "127.0.0.1"
port = 5000

message = ""
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

mensajes_queue = queue.Queue()

def imprimirMensajes():
    while True:
        mensaje = mensajes_queue.get()
        if mensaje == "EXIT":
            break
        print(mensaje)
        mensajes_queue.task_done()
        
threading.Thread(target=imprimirMensajes, daemon=True).start()

def recibirMensaje(new_port):
    new_port = new_port + 50
    m_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    m_socket.bind((host, new_port))
    m_socket.settimeout(5)
    while True:
        try:
            response, server_addr = m_socket.recvfrom(1024)
            mensaje = f"server@{server_addr[0]}:{server_addr[1]} -> {response.decode('utf-8')}"
            mensajes_queue.put(mensaje)
        except socket.timeout:
            pass

def getPort():
    message = "port"
    client_socket.sendto(message.encode("utf-8"), (host, port))
    response, server_addr = client_socket.recvfrom(1024)
    return int(response.decode("utf-8"))

counter = 0

while True:
    if port != 5000:
        try:
            client_socket.settimeout(1)
            response, server_addr = client_socket.recvfrom(1024)
            print(f"server@{server_addr[0]}:{server_addr[1]} -> {response.decode('utf-8')}")
            
            if message.lower() == "q" or message.lower() == "exit":
                break
            
            message = input(f"$ ")
            client_socket.sendto(message.encode("utf-8"), (host, port))
            
        except socket.timeout:
            pass
        
    else:
        print(f"Intentando establecer conexión con el servidor, intento: {counter + 1}")
        try:
            new_port = getPort()
            if new_port > 0:
                port = new_port

                threading.Thread(target=recibirMensaje, args=(new_port,), daemon=True).start()
                
        except Exception as e:
            print(f"Error al obtener el puerto: {e}")
        
        if counter == 2 and port == 5000:
            print(f"Conexión fallida después de {counter + 1} intentos.")
            break
        
    counter += 1

client_socket.close()
