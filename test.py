import random
import json
import time
import os
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

# ---------------- WINDOWS ANSI FIX ----------------
if os.name == "nt":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

# ---------------- SOUND ----------------
try:
    if os.name == "nt":
        import winsound
        def play_tone(freq, dur=120):
            winsound.Beep(freq, dur)
    else:
        raise ImportError
except Exception:
    def play_tone(freq=None, dur=None):
        print("\a", end="")

def sound_correct(): play_tone(880)
def sound_wrong():   play_tone(220)

# ---------------- UTILITIES ----------------
def clear():
    os.system("cls" if os.name == "nt" else "clear")

def flush_input():
    """Best-effort flush of buffered keyboard input (may fail silently on some terminals)."""
    try:
        if os.name == "nt":
            import msvcrt
            while msvcrt.kbhit():
                msvcrt.getch()
        else:
            import sys, termios
            termios.tcflush(sys.stdin, termios.TCIFLUSH)
    except Exception:
        pass

def draw_time_bar(elapsed, limit, T, width=20):
    ratio = min(elapsed / max(limit, 0.001), 1.0)
    filled = int(width * ratio)
    bar = "█" * filled + "░" * (width - filled)
    color = T["green"] if ratio < 0.5 else T["yellow"] if ratio < 0.8 else T["red"]
    print(f"{color}[{bar}] {elapsed:.1f}s / {limit:.1f}s{T['end']}")

# ---------------- PATHS ----------------
BASE_DIR = Path(__file__).absolute().parent if "__file__" in globals() else Path.cwd()
SAVE_FILE = BASE_DIR / "calc_save.json"

# ---------------- CONSTANTS ----------------
NORMAL_TIME = 60.0
MIN_TIME = 15.0
TIME_GRACE = 0.5
MAX_SHIELD = 3
OPS = ["+", "-", "*", "/"]

# ---------------- THEMES ----------------
class Themes:
    CYBERPUNK = {
        "bold": "\033[1m",
        "green": "\033[38;5;121m",
        "red": "\033[38;5;196m",
        "cyan": "\033[38;5;45m",
        "yellow": "\033[38;5;226m",
        "magenta": "\033[38;5;201m",
        "shield": "🛡️ SHIELD ABSORBED HIT",
        "correct": "ACCESS GRANTED",
        "wrong": "TRACE DETECTED",
        "end": "\033[0m",
    }

# ---------------- QUESTION ----------------
class Question:
    def __init__(self, a, b, op, boss=False):
        self.a, self.b, self.op = a, b, op
        self.boss = boss

    @staticmethod
    def generate(streak):
        boss = (streak > 0 and streak % 25 == 0)
        level = max(0, streak // 5)
        op = random.choice(OPS)

        if boss:
            if op == "*":
                a = random.choice([10, 20, 25, 50])
                b = random.randint(12 + level, 25 + level)
            elif op == "/":
                b = random.randint(5, 12)
                a = b * random.randint(10, 25)
            elif op == "+":
                a = random.randint(200, 400)
                b = random.randint(100, 300)
            else:
                a = random.randint(300, 600)
                low, high = sorted((100, a - 50))
                b = random.randint(low, high)
        else:
            if op == "/":
                b = max(1, random.randint(2, 12 + level))
                a = b * random.randint(1, 10 + level)
            elif op == "*":
                a = random.randint(2 + level, 12 + level * 2)
                b = random.randint(2 + level, 12 + level * 2)
            elif op == "-":
                a = random.randint(10, 99 + level * 10)
                b = random.randint(1, max(1, a - 1))
            else:
                a = random.randint(10, 99 + level * 10)
                b = random.randint(1, 12 + level * 2)

        return Question(a, b, op, boss)

    def get_target(self):
        if self.op == "+": return self.a + self.b
        if self.op == "-": return self.a - self.b
        if self.op == "*": return self.a * self.b
        return float(
            (Decimal(self.a) / Decimal(self.b))
            .quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )

# ---------------- GAME STATE ----------------
class GameState:
    def __init__(self):
        self.streak = 0
        self.shield = 1
        self.leaderboard = []
        self.last_milestone = 0
        self.mode = "classic"
        self.load()

    def load(self):
        if SAVE_FILE.exists():
            try:
                data = json.loads(SAVE_FILE.read_text())
                self.leaderboard = [
                    int(s) for s in data.get("leaderboard", [])
                    if str(s).isdigit()
                ]
            except Exception:
                pass

        self.streak = 0
        self.shield = 1
        self.last_milestone = 0
    
    def save(self):
        try:
            SAVE_FILE.write_text(json.dumps({
                "leaderboard": self.leaderboard
            }, indent=2))
        except Exception:
            pass

    def update_leaderboard(self, streak):
        if streak <= 0:
            return
        if streak not in self.leaderboard:
            self.leaderboard.append(streak)
        self.leaderboard = sorted(self.leaderboard, reverse=True)[:5]
        self.save()

# ---------------- GAME ----------------
class MathGame:
    def __init__(self):
        self.gs = GameState()
        self.T = Themes.CYBERPUNK

    def compute_time_limit(self):
        if self.gs.mode == "hyper":
            return max(MIN_TIME, NORMAL_TIME - (self.gs.streak * 0.5))
        return NORMAL_TIME

    def show_result(self, status, target):
        display = int(target) if float(target).is_integer() else target

        if status == "correct":
            print(f"{self.T['green']}{self.T['correct']}{self.T['end']}")
            sound_correct()
        elif status == "wrong":
            print(f"{self.T['red']}{self.T['wrong']} | Answer: {display}{self.T['end']}")
            sound_wrong()
            if self.gs.mode != "hyper":
                time.sleep(1.5)
        elif status == "timeout":
            print(f"{self.T['red']}TIMEOUT | Answer: {display}{self.T['end']}")
            if self.gs.mode != "hyper":
                time.sleep(1.5)

    def run(self):
        clear()
        print(f"{self.T['magenta']}MATH COMMANDER v11.7 [FINAL]{self.T['end']}")
        print("⚠️  Do not type until the answer prompt appears.")
        time.sleep(1.2)

        mode = input("Select mode: [c]lassic | [h]yper-speed > ").strip().lower()
        self.gs.mode = "hyper" if mode == "h" else "classic"

        try:
            while True:
                old_streak = self.gs.streak
                limit = self.compute_time_limit()

                print(f"\nMode: {self.gs.mode.upper()} | Streak: {self.gs.streak} | Shield: {self.gs.shield}/{MAX_SHIELD} | Time: {limit:.1f}s")

                choice = input("c: challenge | q: quit > ").strip().lower()
                if choice == "q":
                    break
                if choice != "c":
                    continue

                clear()

                q = Question.generate(self.gs.streak)
                boss_active = q.boss

                if boss_active:
                    print(f"{self.T['magenta']}⚠️ BOSS LEVEL ⚠️{self.T['end']}")
                    print("⚠️  Hands off the keyboard until the prompt appears.")
                    time.sleep(1.2)

                hint = " (round to 2 decimals)" if q.op == "/" else ""
                print(f"{self.T['bold']}Solve:{self.T['end']} {q.a} {q.op} {q.b}{hint}")

                flush_input()

                start = time.monotonic()
                try:
                    ans = input(f"{self.T['cyan']}= {self.T['end']}").strip()
                except (EOFError, KeyboardInterrupt):
                    break

                elapsed = time.monotonic() - start
                target = q.get_target()

                if elapsed <= limit + TIME_GRACE:
                    draw_time_bar(elapsed, limit, self.T)

                is_correct = False

                if elapsed > limit + TIME_GRACE:
                    self.show_result("timeout", target)
                else:
                    try:
                        if q.op == "/":
                            user = Decimal(ans).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                            if user == Decimal(str(target)):
                                self.show_result("correct", target)
                                self.gs.streak += 1
                                is_correct = True
                            else:
                                self.show_result("wrong", target)
                        else:
                            val = float(ans)
                            if val.is_integer() and int(val) == target:
                                self.show_result("correct", target)
                                self.gs.streak += 1
                                is_correct = True
                            else:
                                self.show_result("wrong", target)
                    except Exception:
                        self.show_result("wrong", target)

                if not is_correct:
                    if self.gs.shield > 0:
                        self.gs.shield -= 1
                        self.gs.shield = max(0, self.gs.shield)
                        print(self.T["shield"])
                    else:
                        self.gs.update_leaderboard(old_streak)
                        self.gs.streak = 0
                        self.gs.last_milestone = 0
                        continue

                if boss_active:
                    self.gs.shield = MAX_SHIELD
                    print("BOSS CLEARED — SHIELDS FULL")
                else:
                    milestone = self.gs.streak // 5
                    if milestone > self.gs.last_milestone:
                        self.gs.last_milestone = milestone
                        if self.gs.shield < MAX_SHIELD:
                            self.gs.shield += 1
                            print("REWARD: Shield +1")

        finally:
            self.gs.update_leaderboard(self.gs.streak)

            print("\n🏆 LEADERBOARD 🏆")
            for i, s in enumerate(self.gs.leaderboard, 1):
                print(f"{i}. {int(s)}")

# ---------------- ENTRY ----------------
if __name__ == "__main__":
    MathGame().run()
