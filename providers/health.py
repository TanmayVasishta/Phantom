from dotenv import load_dotenv
from providers.router import ProviderRouter

def check_providers_health():
    """Run health checks on all configured providers and print the status table."""
    router = ProviderRouter()
    results = router.run_health_checks()
    
    print(f"\n{'Provider':<15}| {'Status':<19}| {'Latency'}")
    print("-" * 45)
    
    ollama_live = False
    
    for res in results:
        status = res["status"]
        lat = res["latency_ms"]
        lat_str = f"{lat}ms" if isinstance(lat, int) else str(lat)
        
        print(f"{res['name']:<15}| {status:<19}| {lat_str}")
        
        if res['name'] == 'Ollama' and status == 'LIVE':
            ollama_live = True

    if not ollama_live:
        print("\n⚠ Local inference unavailable. Using cloud fallback.")
        print("  Your queries will be processed by an external provider.")
        
if __name__ == "__main__":
    load_dotenv()
    check_providers_health()
