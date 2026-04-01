"""
Scheduler -- Windows Task Scheduler 등록.

작업 1 (EtsyAutoShop):     매일 오전 9시 daily_generate.py 실행
작업 2 (EtsyQueueActivate): 매시간 activate_queue.py 실행 (예약 발행 처리)

Usage:
    python scheduler.py --install           # 일일 생성 작업 등록 (9 AM)
    python scheduler.py --install-queue     # 매시간 큐 활성화 작업 등록
    python scheduler.py --install-price     # 매일 가격 자동 인상 작업 등록 (10 AM)
    python scheduler.py --install-pruner    # 매일 리스팅 정리 작업 등록 (11 AM)
    python scheduler.py --install-all       # 위 4개 한 번에 등록
    python scheduler.py --uninstall         # 일일 생성 작업 해제
    python scheduler.py --uninstall-queue   # 큐 활성화 작업 해제
    python scheduler.py --status            # 등록 상태 확인
"""
import argparse
import subprocess
import sys
from pathlib import Path

TASK_NAME         = "EtsyAutoShop"
TASK_NAME_QUEUE   = "EtsyQueueActivate"
TASK_NAME_PRICE   = "EtsyPriceUpdater"
TASK_NAME_PRUNER  = "EtsyListingPruner"
BASE_DIR          = Path(__file__).parent
PYTHON_PATH       = sys.executable
SCRIPT_PATH       = BASE_DIR / "daily_generate.py"
QUEUE_SCRIPT      = BASE_DIR / "activate_queue.py"
PRICE_SCRIPT      = BASE_DIR / "price_updater.py"
PRUNER_SCRIPT     = BASE_DIR / "stale_listing_pruner.py"


def install_task(hour: int = 9, minute: int = 0) -> bool:
    """Register daily generation task in Windows Task Scheduler."""
    cmd = [
        "schtasks", "/Create",
        "/TN", TASK_NAME,
        "/TR", f'"{PYTHON_PATH}" "{SCRIPT_PATH}"',
        "/SC", "DAILY",
        "/ST", f"{hour:02d}:{minute:02d}",
        "/F",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Task '{TASK_NAME}' registered: daily at {hour:02d}:{minute:02d}")
            return True
        else:
            print(f"Failed to register task: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def install_queue_task() -> bool:
    """Register hourly activate_queue.py task in Windows Task Scheduler."""
    cmd = [
        "schtasks", "/Create",
        "/TN", TASK_NAME_QUEUE,
        "/TR", f'"{PYTHON_PATH}" "{QUEUE_SCRIPT}"',
        "/SC", "HOURLY",
        "/MO", "1",   # every 1 hour
        "/F",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Task '{TASK_NAME_QUEUE}' registered: every 1 hour")
            return True
        else:
            print(f"Failed to register queue task: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def install_price_task(hour: int = 10) -> bool:
    """Register daily price updater task (runs after generation)."""
    cmd = [
        "schtasks", "/Create",
        "/TN", TASK_NAME_PRICE,
        "/TR", f'"{PYTHON_PATH}" "{PRICE_SCRIPT}"',
        "/SC", "DAILY",
        "/ST", f"{hour:02d}:30",
        "/F",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Task '{TASK_NAME_PRICE}' registered: daily at {hour:02d}:30")
            return True
        else:
            print(f"Failed to register price task: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def install_pruner_task(hour: int = 11) -> bool:
    """Register daily stale listing pruner task (runs after price updater)."""
    cmd = [
        "schtasks", "/Create",
        "/TN", TASK_NAME_PRUNER,
        "/TR", f'"{PYTHON_PATH}" "{PRUNER_SCRIPT}"',
        "/SC", "DAILY",
        "/ST", f"{hour:02d}:00",
        "/F",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Task '{TASK_NAME_PRUNER}' registered: daily at {hour:02d}:00")
            return True
        else:
            print(f"Failed to register pruner task: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def uninstall_task() -> bool:
    """Remove daily generation task."""
    cmd = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Task '{TASK_NAME}' removed")
            return True
        else:
            print(f"Failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def uninstall_queue_task() -> bool:
    """Remove hourly queue activation task."""
    cmd = ["schtasks", "/Delete", "/TN", TASK_NAME_QUEUE, "/F"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Task '{TASK_NAME_QUEUE}' removed")
            return True
        else:
            print(f"Failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def check_status() -> None:
    """Check registration status of all tasks."""
    for name in [TASK_NAME, TASK_NAME_QUEUE, TASK_NAME_PRICE, TASK_NAME_PRUNER]:
        cmd = ["schtasks", "/Query", "/TN", name]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"[등록됨] {name}")
                print(result.stdout)
            else:
                print(f"[미등록] {name}")
        except Exception as e:
            print(f"Error checking {name}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Etsy Auto Scheduler")
    parser.add_argument("--install",          action="store_true", help="일일 생성 작업 등록 (9 AM)")
    parser.add_argument("--install-queue",    action="store_true", help="매시간 큐 활성화 작업 등록")
    parser.add_argument("--install-price",    action="store_true", help="매일 가격 인상 작업 등록 (10:30 AM)")
    parser.add_argument("--install-pruner",   action="store_true", help="매일 리스팅 정리 작업 등록 (11 AM)")
    parser.add_argument("--install-all",      action="store_true", help="모든 작업 한 번에 등록")
    parser.add_argument("--uninstall",        action="store_true", help="일일 생성 작업 해제")
    parser.add_argument("--uninstall-queue",  action="store_true", help="큐 활성화 작업 해제")
    parser.add_argument("--status",           action="store_true", help="등록 상태 확인")
    parser.add_argument("--hour", type=int, default=9, help="일일 생성 실행 시각 (기본: 9)")
    args = parser.parse_args()

    if args.install_all:
        install_task(hour=args.hour)
        install_queue_task()
        install_price_task()
        install_pruner_task()
        print("✅ 전체 4개 작업 등록 완료")
    elif args.install:
        install_task(hour=args.hour)
    elif args.install_queue:
        install_queue_task()
    elif args.install_price:
        install_price_task()
    elif args.install_pruner:
        install_pruner_task()
    elif args.uninstall:
        uninstall_task()
    elif args.uninstall_queue:
        uninstall_queue_task()
    elif args.status:
        check_status()
    else:
        parser.print_help()
