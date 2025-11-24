import asyncio
import shutil
from rich.console import Console

console = Console()

# 定义你的服务器别名（对应 ~/.ssh/config）
SERVERS = ["server2", "server3", "server4", "server5"]

# 定义远程执行的命令
# query-gpu 参数说明:
# index: 显卡编号
# name: 显卡型号
# utilization.gpu: 核心利用率(%)
# memory.used: 已用显存(MiB)
# memory.total: 总显存(MiB)
# temperature.gpu: 温度(C)
CMD = "nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits"

async def fetch_server_gpu(host):
    """
    异步连接单个服务器并获取数据
    """
    try:
        # 使用 asyncio.create_subprocess_exec 调用系统 ssh 命令
        # 这样会自动使用你的 ~/.ssh/config 配置
        process = await asyncio.create_subprocess_exec(
            "ssh", 
            host, 
            CMD,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # 等待结果，设置超时时间（比如5秒），防止卡死
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)
        
        if process.returncode == 0:
            raw_data = stdout.decode().strip()
            return {"host": host, "status": "OK", "data": raw_data}
        else:
            return {"host": host, "status": "Error", "error": stderr.decode().strip()}
            
    except asyncio.TimeoutError:
        return {"host": host, "status": "Timeout", "error": "连接超时"}
    except Exception as e:
        return {"host": host, "status": "Exception", "error": str(e)}

async def main():
    console.print(f"[bold yellow]开始并发连接 {len(SERVERS)} 台服务器...[/bold yellow]")
    
    # 创建所有任务
    tasks = [fetch_server_gpu(server) for server in SERVERS]
    
    # 并发执行并等待所有结果
    results = await asyncio.gather(*tasks)
    
    console.print("\n[bold cyan]测试结果报告：[/bold cyan]")
    
    for res in results:
        if res['status'] == "OK":
            console.print(f"✅ [bold green]{res['host']}[/bold green]: 数据获取成功")
            # 打印前两行数据作为验证
            lines = res['data'].split('\n')
            for line in lines:
                console.print(f"   └─ {line}")
        else:
            console.print(f"❌ [bold red]{res['host']}[/bold red]: {res['status']} - {res.get('error')}")

if __name__ == "__main__":
    # 检查本地是否有 ssh 命令
    if not shutil.which("ssh"):
        console.print("[bold red]错误：找不到 ssh 命令，请确保在命令行可以运行 ssh[/bold red]")
    else:
        asyncio.run(main())