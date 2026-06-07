import asyncio
from app.services.signalr_client import MemorySignalRClient, run_client_blocking

async def main():
    def on_msg(msg_type, msg_data, timestamp):
        if msg_type in ["SessionInfo", "RaceControlMessages"]:
            print(f"[{msg_type}] {msg_data}")
            
    client = MemorySignalRClient(callback=on_msg, no_auth=True)
    
    # Run it for 10 seconds then stop
    task = asyncio.to_thread(run_client_blocking, client)
    await asyncio.sleep(15)
    # the client doesn't have a stop method, but the script will exit
    print("Done")

if __name__ == "__main__":
    asyncio.run(main())
