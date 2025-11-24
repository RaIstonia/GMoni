import asyncio
import shutil
from datetime import datetime
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.progress import BarColumn, Progress, TextColumn
from rich.box import SIMPLE

# --- 高级配置 ---
SERVERS = ["server2", "server3", "server4", "server5"]
REFRESH_RATE = 3          # 刷新间隔（秒）
SSH_TIMEOUT = 20          # SSH 连接超时时间 (第一次连接可能较慢)
MAX_RETRIES = 1           # 失败重试次数

# SSH 参数优化：
# 1. ControlMaster/Persist: 开启连接复用，第一次慢，后面秒开
# 2. UserKnownHostsFile=/dev/null: 忽略指纹验证，防止卡死
# 3. LogLevel=ERROR: 减少干扰
SSH_OPTS = f"-o ConnectTimeout={SSH_TIMEOUT} -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o GSSAPIAuthentication=no -o ControlMaster=auto -o ControlPath=/tmp/ssh_mux_%h_%p_%r -o ControlPersist=600"
GPU_CMD = "nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits"

# 初始化状态为 "init"
SERVER_STATE = {s: {"status": "init", "data": [], "last_error": ""} for s in SERVERS}

console = Console()

async def fetch_single_server_with_retry(host):
    """带重试机制的获取逻辑"""
    for attempt in range(MAX_RETRIES + 1):
        success = await _fetch_core(host)
        if success:
            return
        if attempt < MAX_RETRIES:
            await asyncio.sleep(1)

async def _fetch_core(host):
    """核心获取逻辑"""
    try:
        full_cmd = f"ssh {SSH_OPTS} {host} '{GPU_CMD}'"
        
        process = await asyncio.create_subprocess_shell(
            full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=SSH_TIMEOUT + 2)

        if process.returncode == 0:
            raw_data = stdout.decode().strip()
            parsed_gpus = []
            if raw_data:
                for line in raw_data.split('\n'):
                    try:
                        parts = [x.strip() for x in line.split(',')]
                        if len(parts) == 5:
                            parsed_gpus.append({
                                "id": parts[0],
                                "util": int(parts[1]),
                                "mem_used": int(parts[2]),
                                "mem_total": int(parts[3]),
                                "temp": int(parts[4])
                            })
                    except ValueError:
                        continue 
            
            SERVER_STATE[host] = {
                "status": "ok",
                "data": parsed_gpus,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "last_error": ""
            }
            return True
        else:
            error_msg = stderr.decode().strip()
            short_err = error_msg.split('\n')[-1] if error_msg else f"Exit Code {process.returncode}"
            
            SERVER_STATE[host] = {
                "status": "error",
                "data": [],
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "last_error": short_err 
            }
            return False
            
    except asyncio.TimeoutError:
        SERVER_STATE[host] = {
            "status": "error", 
            "data": [],
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "last_error": "❌ SSH Timed Out (Network/Firewall?)"
        }
        return False
    except Exception as e:
        SERVER_STATE[host] = {
            "status": "error", 
            "data": [],
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "last_error": f"Exception: {str(e)}"
        }
        return False

def get_color_usage(percent):
    if percent < 30: return "green"
    if percent < 80: return "yellow"
    return "red"

def get_color_temp(temp):
    if temp < 60: return "green"
    if temp < 80: return "yellow"
    return "red bold blink"

def create_bar(percent, width=10):
    color = get_color_usage(percent)
    blocks = int((percent / 100) * width)
    bar_str = "█" * blocks + "░" * (width - blocks)
    return f"[{color}]{bar_str}[/{color}]"

def render_server_panel(host):
    """
    渲染面板逻辑：
    1. init -> 蓝色连接中
    2. error -> 红色报错
    3. ok -> 绿色数据
    """
    state = SERVER_STATE.get(host, {})
    status = state.get("status", "init")
    
    # --- 1. 初始化/连接中状态 (新增逻辑) ---
    if status == "init":
        return Panel(
            "\n[bold cyan]🔄 Connecting...[/bold cyan]\n[dim]Establishing secure channel...[/dim]\n",
            title=f"🖥️ {host}",
            border_style="cyan",
            expand=True
        )

    # --- 2. 错误状态 ---
    if status == "error":
        last_error = state.get("last_error", "Unknown Error")
        if "Timed Out" in last_error:
            advice = "[dim]Check firewall or IP[/dim]"
        elif "Connection refused" in last_error:
            advice = "[dim]Check Port in ~/.ssh/config[/dim]"
        elif "Could not resolve" in last_error:
            advice = "[dim]Check Hostname/DNS[/dim]"
        else:
            advice = ""

        content = f"[bold red]⚠️ CONNECTION FAILED[/bold red]\n\n[white]{last_error}[/white]\n{advice}"
        return Panel(
            content,
            title=f"🖥️ {host}",
            border_style="red",
            expand=True
        )

    # --- 3. 正常数据状态 ---
    gpus = state.get("data", [])
    timestamp = state.get("timestamp", "")
    
    table = Table(show_header=True, header_style="bold white", box=SIMPLE, expand=True, padding=(0,1))
    table.add_column("ID", width=2, justify="right")
    table.add_column("Util %", justify="left", ratio=3)
    table.add_column("Mem %", justify="left", ratio=3)
    table.add_column("Temp", justify="right", width=4)

    for gpu in gpus:
        mem_pct = (gpu['mem_used'] / gpu['mem_total']) * 100 if gpu['mem_total'] > 0 else 0
        util_bar = create_bar(gpu['util'], width=8)
        mem_bar = create_bar(mem_pct, width=8)
        temp_styled = f"[{get_color_temp(gpu['temp'])}]{gpu['temp']}°C[/]"
        
        table.add_row(
            str(gpu['id']),
            f"{util_bar} {gpu['util']}%",
            f"{mem_bar} {int(mem_pct)}%",
            temp_styled
        )

    return Panel(
        table,
        title=f"🖥️ [bold green]{host}[/] [dim]({timestamp})[/dim]",
        border_style="green",
        expand=True
    )

def generate_dashboard():
    grid = Table.grid(expand=True, padding=1)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    
    # 这里动态生成行，防止手动写死 index out of range
    num_servers = len(SERVERS)
    for i in range(0, num_servers, 2):
        s1 = SERVERS[i]
        s2 = SERVERS[i+1] if (i+1) < num_servers else None
        
        p1 = render_server_panel(s1)
        p2 = render_server_panel(s2) if s2 else Panel("", border_style="black") # 占位空面板
        
        grid.add_row(p1, p2)
    
    return grid

async def update_loop(live):
    while True:
        # 并发获取所有数据
        # 注意：这里会改变 SERVER_STATE 里的 status
        tasks = [fetch_single_server_with_retry(s) for s in SERVERS]
        await asyncio.gather(*tasks)
        
        # 数据更新后，Live 上下文会自动调用 generate_dashboard 重绘
        # 但我们需要手动 update 一次以防万一
        live.update(generate_dashboard())
        
        await asyncio.sleep(REFRESH_RATE)

def main():
    if not shutil.which("ssh"):
        print("Error: ssh command not found.")
        return

    layout = generate_dashboard()
    
    # 启动 Live 渲染
    with Live(layout, refresh_per_second=4, screen=True) as live:
        try:
            asyncio.run(update_loop(live))
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()