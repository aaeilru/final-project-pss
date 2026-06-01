import requests
import time

BASE_URL = "http://localhost:8000/api/v1"
ITERATIONS = 50


def benchmark_endpoint(url, label):
    """Mengukur rata-rata response time sebuah endpoint."""
    times = []
    success = 0
    failed = 0

    for i in range(ITERATIONS):
        start = time.time()
        response = requests.get(url)
        elapsed = (time.time() - start) * 1000

        if response.status_code == 200:
            times.append(elapsed)
            success += 1
        else:
            failed += 1
            print(f"Request gagal: {response.status_code} - {response.text}")

    if not times:
        print(f"\n{label}")
        print("Tidak ada request yang berhasil.")
        return 0

    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)

    print(f"\n{label}")
    print(f"  Success   : {success}")
    print(f"  Failed    : {failed}")
    print(f"  Rata-rata : {avg_time:.2f} ms")
    print(f"  Minimum   : {min_time:.2f} ms")
    print(f"  Maksimum  : {max_time:.2f} ms")

    return avg_time


print("=" * 50)
print("BENCHMARK: Simple LMS API Performance")
print("=" * 50)

avg_courses = benchmark_endpoint(
    f"{BASE_URL}/courses/",
    "GET /courses/"
)

avg_detail = benchmark_endpoint(
    f"{BASE_URL}/courses/1",
    "GET /courses/1"
)

print("\nRingkasan")
print(f"GET /courses/   : {avg_courses:.2f} ms")
print(f"GET /courses/1  : {avg_detail:.2f} ms")