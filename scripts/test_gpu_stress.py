#!/usr/bin/env python3
"""
Stress test GPU with realistic workloads that will show CPU/GPU spikes.
"""

import time
import torch
import psutil
import threading
from sentence_transformers import SentenceTransformer

def monitor_usage():
    """Monitor CPU and GPU usage in background."""
    try:
        import GPUtil
        
        while monitor_usage.running:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # GPU usage
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]
                gpu_load = gpu.load * 100
                gpu_memory = gpu.memoryUsed
                
                print(f"📊 CPU: {cpu_percent:5.1f}% | GPU: {gpu_load:5.1f}% | VRAM: {gpu_memory:4.0f}MB", end="\r")
            
            time.sleep(0.5)
    except Exception as e:
        print(f"Monitoring error: {e}")

def stress_test_cpu_vs_gpu():
    """Heavy stress test with large datasets."""
    print("🔥 Heavy Stress Test - You Should See CPU/GPU Spikes!")
    print("=" * 60)
    
    # Create a much larger, more realistic dataset
    base_documents = [
        "Our company policy for remote work includes flexible scheduling, home office setup requirements, communication protocols, productivity expectations, and team collaboration guidelines. Employees must maintain regular hours, participate in daily standups, use company-approved security software, and ensure reliable internet connectivity for video conferencing and file sharing.",
        
        "The vacation policy offers unlimited paid time off with manager approval, requiring two weeks advance notice for extended absences, coordination with team members for coverage, and blackout periods during critical project phases. Employees should balance personal time with business needs, document handoff procedures, and maintain project continuity.",
        
        "Company culture emphasizes innovation, ownership, continuous learning, fast decision-making, customer obsession, and high-impact results. We value transparency, constructive feedback, risk-taking in pursuit of breakthrough solutions, cross-functional collaboration, and maintaining work-life balance while delivering exceptional outcomes.",
        
        "Employee benefits include comprehensive health insurance with 90% company coverage, dental and vision plans, 401k matching up to 6%, life insurance, disability coverage, mental health support, fitness reimbursements, professional development funds, conference attendance, and education assistance programs for skill advancement.",
        
        "Remote work equipment provided includes laptop, monitor, ergonomic chair, desk setup allowance, high-speed internet reimbursement, noise-canceling headphones, webcam, security software licenses, and access to productivity tools. Employees must maintain secure home office environments and follow data protection protocols.",
        
        "Professional development opportunities encompass internal training programs, external course reimbursement, mentorship matching, cross-team project assignments, conference presentations, skill-building workshops, leadership development tracks, and career advancement planning with regular performance reviews and goal setting.",
        
        "Team collaboration tools include Slack for communication, Zoom for video meetings, GitHub for code collaboration, Notion for documentation, Figma for design work, Jira for project tracking, and shared calendars for scheduling. All tools require two-factor authentication and regular security updates.",
        
        "Performance review process involves quarterly check-ins, annual comprehensive evaluations, 360-degree feedback collection, goal setting and tracking, career development discussions, compensation reviews, promotion considerations, and professional growth planning with clear advancement criteria and expectations.",
        
        "Onboarding program spans the first 90 days with buddy assignments, department introductions, system access setup, security training completion, company culture immersion, role-specific skill development, project shadowing, and regular manager check-ins to ensure successful integration.",
        
        "Innovation initiatives encourage experimentation, hackathon participation, idea submission processes, cross-functional collaboration, customer research involvement, prototype development, patent applications, technology exploration, and allocated time for creative projects that align with company objectives."
    ]
    
    # Create massive dataset (1000+ queries)
    stress_dataset = []
    for i in range(100):  # 100 iterations
        for doc in base_documents:
            # Add variations to make it more realistic
            variations = [
                f"Query {i}: {doc}",
                f"Analysis request: {doc}",
                f"Detailed explanation of: {doc}",
                f"How does this relate to: {doc}",
                f"Implementation guide for: {doc}"
            ]
            stress_dataset.extend(variations)
    
    print(f"📊 Created stress dataset: {len(stress_dataset)} documents")
    print(f"📝 Average document length: {sum(len(d) for d in stress_dataset) / len(stress_dataset):.0f} chars")
    
    # Start monitoring
    monitor_usage.running = True
    monitor_thread = threading.Thread(target=monitor_usage, daemon=True)
    monitor_thread.start()
    
    print(f"\n⚙️  CPU Stress Test (this will take ~30-60 seconds)...")
    model_cpu = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cpu')
    
    start = time.time()
    embeddings_cpu = model_cpu.encode(stress_dataset, batch_size=16, show_progress_bar=True)
    cpu_time = time.time() - start
    
    print(f"\n   CPU Results:")
    print(f"   Time: {cpu_time:.1f}s")
    print(f"   Rate: {len(stress_dataset)/cpu_time:.1f} docs/sec")
    print(f"   Shape: {embeddings_cpu.shape}")
    
    time.sleep(2)  # Brief pause
    
    print(f"\n🔥 GPU Stress Test (should be much faster and show GPU spike)...")
    model_gpu = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cuda')
    
    # Warmup
    model_gpu.encode(["warmup"], show_progress_bar=False)
    torch.cuda.synchronize()
    
    start = time.time()
    embeddings_gpu = model_gpu.encode(stress_dataset, batch_size=32, show_progress_bar=True)
    torch.cuda.synchronize()
    gpu_time = time.time() - start
    
    print(f"\n   GPU Results:")
    print(f"   Time: {gpu_time:.1f}s")
    print(f"   Rate: {len(stress_dataset)/gpu_time:.1f} docs/sec")
    print(f"   Shape: {embeddings_gpu.shape}")
    print(f"   Memory: {torch.cuda.memory_allocated() / 1024**3:.1f} GB")
    
    print(f"\n🎯 Final Results:")
    print(f"   GPU Speedup: {cpu_time/gpu_time:.1f}x")
    print(f"   Total documents: {len(stress_dataset)}")
    
    # Stop monitoring
    monitor_usage.running = False
    time.sleep(1)

def continuous_load_test():
    """Continuous load for sustained monitoring."""
    print(f"\n🔄 Continuous Load Test (30 seconds)")
    print("Watch your system monitor for sustained GPU usage!")
    print("=" * 60)
    
    model_gpu = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cuda')
    
    # Realistic continuous queries
    test_query = "Comprehensive analysis of remote work productivity metrics and employee satisfaction surveys across distributed teams with varying timezone coverage and communication patterns."
    
    # Start monitoring
    monitor_usage.running = True
    monitor_thread = threading.Thread(target=monitor_usage, daemon=True)
    monitor_thread.start()
    
    start_time = time.time()
    query_count = 0
    
    print("Running continuous embedding generation...")
    
    while time.time() - start_time < 30:  # Run for 30 seconds
        # Generate embeddings in batches
        batch = [test_query] * 20
        embeddings = model_gpu.encode(batch, show_progress_bar=False)
        query_count += len(batch)
        
        # Small delay to see sustained usage
        time.sleep(0.1)
    
    monitor_usage.running = False
    
    total_time = time.time() - start_time
    print(f"\n📊 Continuous Load Results:")
    print(f"   Duration: {total_time:.1f}s")
    print(f"   Queries processed: {query_count}")
    print(f"   Average rate: {query_count/total_time:.1f} queries/sec")

def main():
    """Run comprehensive stress tests."""
    if not torch.cuda.is_available():
        print("❌ CUDA not available")
        return
    
    print("🚀 RTX 5070 GPU Stress Test Suite")
    print("=" * 60)
    print("This will generate significant CPU and GPU load!")
    print("Watch your system monitor to see the spikes!")
    print("")
    
    try:
        stress_test_cpu_vs_gpu()
        continuous_load_test()
        
        print(f"\n✅ Stress test complete!")
        print(f"You should have seen:")
        print(f"• CPU usage spikes during CPU test")
        print(f"• GPU usage spikes during GPU test") 
        print(f"• Significant speedup on RTX 5070")
        print(f"• GPU memory usage during inference")
        
    except KeyboardInterrupt:
        print(f"\n⚠️  Test interrupted by user")
        monitor_usage.running = False

if __name__ == "__main__":
    main()