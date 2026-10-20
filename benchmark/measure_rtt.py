#!/usr/bin/env python3
"""
RTT Measurement Script for C2C Order Grabber Bot

Measures network latency to api.cards2cards.com including:
- DNS resolution time
- TCP handshake time (1 RTT)
- TLS handshake time (2-3 RTT)
- Time to first byte (TTFB)
"""

import socket
import ssl
import time
import statistics
import json
import sys
from urllib.parse import urlparse


def measure_dns(hostname: str) -> tuple[str, float]:
    """Measure DNS resolution time and return IP + duration"""
    start = time.perf_counter()
    ip_address = socket.gethostbyname(hostname)
    duration = time.perf_counter() - start
    return ip_address, duration


def measure_tcp_handshake(ip: str, port: int, timeout: float = 5.0) -> float:
    """Measure TCP handshake time (1 RTT)"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        start = time.perf_counter()
        sock.connect((ip, port))
        duration = time.perf_counter() - start
        return duration
    finally:
        sock.close()


def measure_tls_handshake(hostname: str, ip: str, port: int, timeout: float = 5.0) -> float:
    """Measure TLS handshake time (includes TCP + TLS)"""
    context = ssl.create_default_context()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        start = time.perf_counter()
        sock.connect((ip, port))
        ssl_sock = context.wrap_socket(sock, server_hostname=hostname)
        duration = time.perf_counter() - start
        ssl_sock.close()
        return duration
    finally:
        sock.close()


def measure_http_request(hostname: str, ip: str, port: int, path: str = "/", timeout: float = 10.0) -> float:
    """Measure full HTTP request time (DNS + TCP + TLS + HTTP)"""
    context = ssl.create_default_context()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        start = time.perf_counter()

        # TCP handshake
        sock.connect((ip, port))

        # TLS handshake
        ssl_sock = context.wrap_socket(sock, server_hostname=hostname)

        # HTTP request
        request = f"GET {path} HTTP/1.1\r\nHost: {hostname}\r\nConnection: close\r\n\r\n"
        ssl_sock.sendall(request.encode())

        # Read first byte of response
        ssl_sock.recv(1)

        duration = time.perf_counter() - start
        ssl_sock.close()
        return duration
    finally:
        sock.close()


def run_benchmark(url: str, runs: int = 20) -> dict:
    """Run comprehensive RTT benchmark"""
    parsed = urlparse(url)
    hostname = parsed.netloc
    port = 443 if parsed.scheme == "https" else 80
    path = parsed.path or "/"

    print(f"🔍 Benchmarking: {url}")
    print(f"   Hostname: {hostname}")
    print(f"   Runs: {runs}")
    print()

    # DNS resolution (once, with cache warmup)
    print("📡 DNS Resolution...")
    ip_address, _ = measure_dns(hostname)  # Warmup
    time.sleep(0.5)
    dns_times = []
    for i in range(3):
        _, dns_time = measure_dns(hostname)
        dns_times.append(dns_time * 1000)  # Convert to ms
        time.sleep(0.1)

    print(f"   IP: {ip_address}")
    print(f"   DNS time: {statistics.mean(dns_times):.2f}ms (avg of 3)")
    print()

    # TCP handshake measurements
    print("🔌 TCP Handshake (RTT)...")
    tcp_times = []
    for i in range(runs):
        try:
            tcp_time = measure_tcp_handshake(ip_address, port)
            tcp_times.append(tcp_time * 1000)  # Convert to ms
            print(f"   Run {i+1}/{runs}: {tcp_time*1000:.2f}ms", end="\r")
            time.sleep(0.2)  # Small delay between measurements
        except Exception as e:
            print(f"\n   ⚠️  Run {i+1} failed: {e}")
    print()

    # TLS handshake measurements
    print("🔐 TLS Handshake (TCP + TLS)...")
    tls_times = []
    for i in range(runs):
        try:
            tls_time = measure_tls_handshake(hostname, ip_address, port)
            tls_times.append(tls_time * 1000)  # Convert to ms
            print(f"   Run {i+1}/{runs}: {tls_time*1000:.2f}ms", end="\r")
            time.sleep(0.2)
        except Exception as e:
            print(f"\n   ⚠️  Run {i+1} failed: {e}")
    print()

    # HTTP request measurements
    print("🌐 HTTP Request (Full round-trip)...")
    http_times = []
    for i in range(runs):
        try:
            http_time = measure_http_request(hostname, ip_address, port, path)
            http_times.append(http_time * 1000)  # Convert to ms
            print(f"   Run {i+1}/{runs}: {http_time*1000:.2f}ms", end="\r")
            time.sleep(0.3)
        except Exception as e:
            print(f"\n   ⚠️  Run {i+1} failed: {e}")
    print()

    # Calculate statistics
    def calc_stats(times: list[float]) -> dict:
        if not times:
            return {"min": 0, "max": 0, "mean": 0, "median": 0, "p95": 0, "p99": 0, "stdev": 0}

        sorted_times = sorted(times)
        n = len(sorted_times)

        return {
            "min": min(times),
            "max": max(times),
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "p95": sorted_times[int(n * 0.95)] if n > 0 else 0,
            "p99": sorted_times[int(n * 0.99)] if n > 0 else 0,
            "stdev": statistics.stdev(times) if len(times) > 1 else 0,
        }

    results = {
        "url": url,
        "hostname": hostname,
        "ip_address": ip_address,
        "runs": runs,
        "dns": calc_stats(dns_times),
        "tcp_handshake": calc_stats(tcp_times),
        "tls_handshake": calc_stats(tls_times),
        "http_request": calc_stats(http_times),
        "estimated_rtt_ms": statistics.median(tcp_times) if tcp_times else 0,
    }

    return results


def print_results(results: dict):
    """Print formatted results"""
    print("\n" + "="*60)
    print("📊 BENCHMARK RESULTS")
    print("="*60)
    print(f"URL: {results['url']}")
    print(f"IP:  {results['ip_address']}")
    print(f"Runs: {results['runs']}")
    print()

    print(f"{'Metric':<20} {'Min':>8} {'Median':>8} {'Mean':>8} {'P95':>8} {'P99':>8} {'Max':>8} {'StdDev':>8}")
    print("-" * 100)

    for metric_name, display_name in [
        ("dns", "DNS Resolution"),
        ("tcp_handshake", "TCP Handshake"),
        ("tls_handshake", "TLS Handshake"),
        ("http_request", "HTTP Request"),
    ]:
        stats = results[metric_name]
        print(
            f"{display_name:<20} "
            f"{stats['min']:>7.1f}ms "
            f"{stats['median']:>7.1f}ms "
            f"{stats['mean']:>7.1f}ms "
            f"{stats['p95']:>7.1f}ms "
            f"{stats['p99']:>7.1f}ms "
            f"{stats['max']:>7.1f}ms "
            f"{stats['stdev']:>7.1f}ms"
        )

    print()
    print(f"🎯 Estimated RTT (TCP handshake median): {results['estimated_rtt_ms']:.1f}ms")
    print("="*60)


if __name__ == "__main__":
    # Configuration
    TARGET_URL = "https://api.cards2cards.com"
    NUM_RUNS = 20

    # Allow override from command line
    if len(sys.argv) > 1:
        TARGET_URL = sys.argv[1]
    if len(sys.argv) > 2:
        NUM_RUNS = int(sys.argv[2])

    try:
        results = run_benchmark(TARGET_URL, NUM_RUNS)
        print_results(results)

        # Output JSON for automation
        print("\n📄 JSON Output:")
        print(json.dumps(results, indent=2))

    except KeyboardInterrupt:
        print("\n\n⚠️  Benchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
