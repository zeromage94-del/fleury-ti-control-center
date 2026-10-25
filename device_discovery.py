"""Descoberta limitada a segmentos privados autorizados; sem autenticação ou mudanças."""
import ipaddress
import socket

PORTS = (5985, 5986, 3389, 445, 9100, 631, 443, 80)
TCP_TIMEOUT = 0.6


def classify(ports):
    ports = set(ports)
    if ports & {5985, 5986, 3389, 445}:
        return 'computer', 'Serviço de computador detectado; confirmar no inventário Windows.'
    if ports & {9100, 631}:
        return 'printer', 'Serviço de impressão detectado; classificação provável.'
    return 'unknown', 'Tipo não confirmado; classifique após verificar o equipamento.'


def probe(target, ping, timeout=TCP_TIMEOUT):
    """Probe each known service without treating blocked ICMP as an outage.

    The timeout is a bound for one connection, not a claim that every live host
    responds within it. Slower/filtered networks can still require manual entry.
    """
    opened = []
    timed_out = 0
    for port in PORTS:
        try:
            with socket.create_connection((target, port), timeout=timeout):
                opened.append(port)
        except TimeoutError:
            timed_out += 1
        except OSError:
            continue
    alive = bool(opened) or ping(target)
    kind, evidence = classify(opened)
    return {'alive': alive, 'device_type': kind, 'evidence': evidence,
            'ports': opened, 'timed_out_ports': timed_out}


def validate_segments(values):
    if not isinstance(values, list) or not 1 <= len(values) <= 8:
        raise ValueError('Informe de 1 a 8 segmentos privados, com até 4096 endereços no total.')
    result = []
    blocks = [ipaddress.ip_network(x) for x in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')]
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError('Segmento inválido.')
        try:
            subnet = ipaddress.ip_network(value, strict=False)
        except (TypeError, ValueError) as exc:
            raise ValueError('Segmento inválido.') from exc
        if subnet.version != 4 or subnet.num_addresses > 4096 or not any(subnet.subnet_of(b) for b in blocks):
            raise ValueError('Use segmentos IPv4 privados de /20 ou menores, até 4096 endereços no total.')
        if str(subnet) not in result:
            result.append(str(subnet))
    collapsed=list(ipaddress.collapse_addresses(ipaddress.ip_network(x) for x in result))
    if sum(n.num_addresses for n in collapsed)>4096:
        raise ValueError('Limite de 4096 endereços por descoberta. Divida a rede em segmentos.')
    return [str(n) for n in collapsed]
