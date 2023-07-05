import socket

ADDR = "localhost"
PORT = 8466

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((ADDR, PORT))
server_socket.listen(10)

connection, addr = server_socket.accept()
print("[INFO]\t", addr, "connected")

msg = connection.recv(1024).decode()
print("[INFO]\tReceived message:", msg)

response = "Hello"
connection.send(response.encode())

connection.close()
server_socket.close()
