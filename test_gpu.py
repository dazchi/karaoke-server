import torch
import time

def fill_vram():
    # Ensure CUDA is available
    if not torch.cuda.is_available():
        print("CUDA is not available. Testing aborted.")
        return

    device = torch.device("cuda:0")
    print(f"Using device: {torch.cuda.get_device_name(0)}")
    
    # List to hold tensors to keep them in memory
    vram_holder = []
    
    # Size of each allocation (~100MB)
    chunk_size = 1024 * 1024 * 25  # 25 million float32 elements
    
    try:
        print("Starting to fill VRAM...")
        while True:
            # Allocate tensor on GPU
            vram_holder.append(torch.ones(chunk_size, device=device))
            
            # Print current allocated memory (approximate)
            current_vram = torch.cuda.memory_allocated(device) / 1024**3
            print(f"Allocated VRAM: {current_vram:.2f} GB", end='\r')
            
            time.sleep(0.1) # Small delay to stabilize
            
    except RuntimeError as e:
        print("\n" + "="*30)
        print("VRAM filled or Out of Memory!")
        print("="*30)
        print(e)
    finally:
        # Clear cache
        del vram_holder
        torch.cuda.empty_cache()
        print("VRAM cleared.")

if __name__ == "__main__":
    fill_vram()
