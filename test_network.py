import socket

ips = ["5.75.250.104"]
ports = [22, 80, 443, 8501, 9007]

for ip in ips:
    print(f"\n--- Testing IP {ip} ---")
    for port in ports:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        try:
            res = s.connect_ex((ip, port))
            if res == 0:
                print(f" [OPEN] Port {port} is OPEN on {ip}")
            else:
                print(f" [CLOSED/FILTERED] Port {port} code {res}")
        except Exception as e:
            print(f" [ERROR] Port {port} -> {e}")
        finally:
            s.close()
