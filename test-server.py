#!/usr/bin/env python3
import socket

# For testing the messages sent by other scripts

TCP_IP = 'localhost'
TCP_PORT = 5041
BUFFER_SIZE = 1024

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((TCP_IP, TCP_PORT))
s.listen(1)
print("Now listening on HOST " + TCP_IP + " PORT " + str(TCP_PORT))
conn, addr = s.accept()
print('Connection address:', addr)
while True:
    data = conn.recv(BUFFER_SIZE)
    if not data:
        continue
    print("received data:", data)
conn.close()
