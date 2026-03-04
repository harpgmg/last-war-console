import os
import sys
import time
import json
import random

ANSI = sys.stdout.isatty()

## ---------- Constants ----------
BANNER = r"""
=====================================================================================
   _                _     __        __            ____                      _
  | |    __ _  ___ | |_   \ \      / /_ _ _ __   / ___|___  _ __  ___  ___ | | ___
  | |   / _` |/ __|| __|   \ \ /\ / / _` | '__| | |   / _ \| '_ \/ __|/ _ \| |/ _ \
  | |__| (_| |\__ \| |_     \ V  V / (_| | |    | |__| (_) | | | \__ \ (_) | |  __/
  |_____\__,_||___/ \__|     \_/\_/ \__,_|_|     \____\___/|_| |_|___/\___/|_|\___|

=====================================================================================
"""

## ---------- Helper functions ----------
def c(text, code):
    return f"\033[{code}m{text}\033[0m" if ANSI else text

def clear():
    os.system("cls" if os.name == "nt" else "clear")

# persistent storage for leadership names
LEADER_FILE = os.path.join(os.path.dirname(__file__), "leaders.json")

def load_leaders():
    """Return list of leader objects from disk; empty list if none.
    
    Migrates old string format to new object format with name and status.
    """
    try:
        with open(LEADER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                # migrate old string format to new object format
                migrated = []
                for item in data:
                    if isinstance(item, str):
                        # old format: just a name
                        migrated.append({
                            "name": item,
                            "status": "active"
                        })
                    else:
                        # already new format, ensure all fields exist
                        migrated.append({
                            "name": item.get("name", "Unknown"),
                            "status": item.get("status", "active")
                        })
                return migrated
    except FileNotFoundError:
        return []
    except Exception:
        # corrupted file - start fresh
        return []
    return []

def save_leaders(leaders):
    """Persist list of names to disk."""
    try:
        with open(LEADER_FILE, "w", encoding="utf-8") as f:
            json.dump(leaders, f, indent=2)
    except Exception as e:
        print(f"Error saving leaders: {e}")

# general config storage
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    """Return general config object; empty dict if none."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    return {}

def save_config(config):
    """Persist config object to disk."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")

# train history storage (track all names and their conductor/vip counts)
TRAIN_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "train_history.json")

def load_train_history():
    """Return dict of {name: {conductor_count, vip_count}}; empty dict if none."""
    try:
        with open(TRAIN_HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except FileNotFoundError:
        return {}
    except Exception:
        return {}
    return {}

def save_train_history(history):
    """Persist train history dict to disk."""
    try:
        with open(TRAIN_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Error saving train history: {e}")

def update_counts_from_past_schedule(leaders, schedule):
    """Scan schedule for entries between last_scan_date and today and update train history.

    Uses `config.json` -> `last_scan_date` to avoid double-counting. Returns the
    newest date processed (or existing last_scan_date if nothing processed).
    """
    from datetime import date
    today = date.today().isoformat()

    # load existing train history and config
    history = load_train_history()
    config = load_config()
    last_scan = config.get('last_scan_date')

    newest_processed = last_scan
    processed_any = False

    # scan all entries older than today but after last_scan
    for entry in schedule:
        d = entry.get('date')
        if not d:
            continue
        # skip future/today entries
        if d >= today:
            continue
        # skip already-scanned entries
        if last_scan and d <= last_scan:
            continue

        # process this entry
        if entry.get('conductor'):
            name = entry['conductor']
            if name not in history:
                history[name] = {"conductor_count": 0, "vip_count": 0}
            history[name]['conductor_count'] = history[name].get('conductor_count', 0) + 1
        if entry.get('vip'):
            name = entry['vip']
            if name not in history:
                history[name] = {"conductor_count": 0, "vip_count": 0}
            history[name]['vip_count'] = history[name].get('vip_count', 0) + 1

        processed_any = True
        if newest_processed is None or d > newest_processed:
            newest_processed = d

    if processed_any:
        save_train_history(history)
        # update config with newest processed date
        config['last_scan_date'] = newest_processed
        save_config(config)

    return newest_processed


def dot_loader(duration: float = 3.0, message: str = "Loading", max_dots: int = 3, interval: float = 0.4):
    """
    Shows: Loading. Loading.. Loading... (loops) for `duration` seconds.
    """
    if not sys.stdout.isatty():
        print(f"{message}...")
        time.sleep(duration)
        return

    start = time.time()
    dots = 0
    while (time.time() - start) < duration:
        dots = (dots % max_dots) + 1
        line = f"{message}{'.' * dots}"
        # Pad with spaces so shorter lines overwrite longer ones cleanly
        pad = " " * (max_dots - dots)
        sys.stdout.write(c("\r" + line + pad, "1;36"))  # bold cyan
        sys.stdout.flush()
        time.sleep(interval)

    # Clear the loader line
    sys.stdout.write("\r" + " " * (len(message) + max_dots) + "\r")
    sys.stdout.flush()

def header(text=""):
    clear()
    # strip leading/trailing newlines from the banner so subtitle sits immediately below
    banner_content = BANNER.strip("\n")
    print(c(banner_content, "1;36"))
    if text:
        # center the subtitle beneath the banner and underline it
        banner_lines = banner_content.splitlines()
        width = max(len(line) for line in banner_lines)
        centered = text.center(width)
        print(c(centered, "1;36"))
        print(c("=" * width, "1;36"))

## ---------- Application ----------
def main_menu():
    # Load and update leader counts from past schedule on app startup
    leaders = load_leaders()
    schedule = load_schedule()
    if schedule:
        last_scanned = update_counts_from_past_schedule(leaders, schedule)
        config = load_config()
        config['last_scan_date'] = last_scanned
        save_config(config)
        save_leaders(leaders)
    
    while True:
        header("Main Menu")
        print("1.) Leadership")
        print("2.) Train Schedule")
        print("3.) Exit")
        print("\n")
        choice = input("Select an option: ")

        if choice == '1':
            leadership_menu()
        elif choice == '2':
            schedule_menu()
        elif choice == '3':
            ##clear()
            print("\n")
            dot_loader(2.0, "Exiting", max_dots=4, interval=0.35)
            clear()
            print(c("Exited Last War Console.", "1;36"))
            return
        else:
            print("Invalid choice. Please try again.")


def leadership_menu():
    leaders = load_leaders()
    while True:
        header("Leadership Menu")
        print("1.) List")
        print("2.) Add")
        print("3.) Find")
        print("4.) Delete")
        print("5.) Back")
        print("\n")
        choice = input("Select an option: ")

        if choice == '1':
            clear()
            print(c("Current Leaders:", "1;36"))
            if not leaders:
                print("  (none)")
            else:
                for idx, leader in enumerate(leaders, start=1):
                    print(f"  {idx}. {leader['name']}")
                    print(f"      {c('Status: ', '1;36')}{leader.get('status', 'active')}")
            input("\nPress Enter to continue...")
        elif choice == '2':
            print("\n")
            name = input("Enter leader name: ").strip()
            if name:
                leaders.append({
                    "name": name,
                    "status": "active"
                })
                save_leaders(leaders)
                print(f"Added '{name}'")
            else:
                print("No name entered.")
            time.sleep(1)
        elif choice == '3':
            print("\n")
            search_name = input("Enter leader name to find: ").strip()
            clear()
            if not search_name:
                print("No name entered.")
                input("\nPress Enter to continue...")
            else:
                from difflib import get_close_matches
                leader_names = [l['name'] for l in leaders]
                search_lower = search_name.lower()
                
                # first try prefix/starts with match
                prefix_matches = [name for name in leader_names if name.lower().startswith(search_lower)]
                
                if prefix_matches:
                    matches = prefix_matches
                else:
                    # fall back to fuzzy matching with lower cutoff
                    matches = get_close_matches(search_name, leader_names, n=5, cutoff=0.3)
                
                if not matches:
                    print(f"No leaders found matching '{search_name}'.")
                    input("\nPress Enter to continue...")
                elif len(matches) == 1:
                    # exact or very close match
                    found_name = matches[0]
                    for leader in leaders:
                        if leader['name'] == found_name:
                            print(c(f"Leader: {leader['name']}", "1;36"))
                            print(f"  {c('Status: ', '1;36')}{leader.get('status', 'active')}")
                            break
                    input("\nPress Enter to continue...")
                else:
                    # multiple matches - let user choose
                    print(c("Multiple matches found:", "1;36"))
                    for idx, match in enumerate(matches, start=1):
                        print(f"  {idx}. {match}")
                    sel = input("Select a leader (number or blank to cancel): ").strip()
                    if sel.isdigit():
                        idx = int(sel) - 1
                        if 0 <= idx < len(matches):
                            found_name = matches[idx]
                            for leader in leaders:
                                if leader['name'] == found_name:
                                    print(c(f"Leader: {leader['name']}", "1;36"))
                                    print(f"  {c('Status: ', '1;36')}{leader.get('status', 'active')}")
                                    break
                        else:
                            print("Invalid selection.")
                    else:
                        print("Canceled.")
                    input("\nPress Enter to continue...")
        elif choice == '4':
            if not leaders:
                print("No leaders to delete.")
                time.sleep(1)
            else:
                clear()
                print(c("Deactivate which leader?", "1;36"))
                for idx, leader in enumerate(leaders, start=1):
                    print(f"  {idx}. {leader['name']}")
                
                print("\n")
                sel = input("Enter number (or blank to cancel): ").strip()
                if sel.isdigit():
                    idx = int(sel) - 1
                    if 0 <= idx < len(leaders):
                        leaders[idx]['status'] = 'inactive'
                        save_leaders(leaders)
                        print(f"Deactivated '{leaders[idx]['name']}'")
                    else:
                        print("Invalid index.")
                else:
                    print("Canceled.")
                time.sleep(1)
        elif choice == '5':
            return
        else:
            print("Invalid choice. Please try again.")

# schedule persistence
SCHEDULE_FILE = os.path.join(os.path.dirname(__file__), "schedule.json")
# queue persistence (members to reward)
QUEUE_FILE = os.path.join(os.path.dirname(__file__), "queue.json")


def load_schedule():
    """Return a previously generated schedule or an empty list.

    If an old-style entry (with "leader" and "role") is detected it will be
    converted in memory to the newer conductor/vip format so callers can work
    uniformly.
    """
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                # migrate old entries if necessary
                migrated = []
                for entry in data:
                    if "leader" in entry and "role" in entry:
                        # convert
                        if entry["role"] == "Conductor":
                            migrated.append({
                                "date": entry["date"],
                                "conductor": entry["leader"],
                                "vip": "",
                            })
                        else:
                            migrated.append({
                                "date": entry["date"],
                                "conductor": "",
                                "vip": entry["leader"],
                            })
                    else:
                        migrated.append(entry)
                return migrated
    except FileNotFoundError:
        return []
    except Exception:
        # corrupted file - ignore and start fresh
        return []
    return []


def save_schedule(schedule):
    """Persist schedule list to disk."""
    try:
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump(schedule, f, indent=2)
    except Exception as e:
        print(f"Error saving schedule: {e}")


def load_queue():
    """Return list of queued member names; empty list if none."""
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except FileNotFoundError:
        return []
    except Exception:
        return []
    return []


def save_queue(queue):
    """Persist queue list to disk."""
    try:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, indent=2)
    except Exception as e:
        print(f"Error saving queue: {e}")


def generate_schedule(leaders, start_date=None, interval_days: int = 1):
    """Generate the next block of schedule entries.

    Entries are dictionaries containing `date`, `conductor` and `vip` keys.
    The first pass fills the conductor column and leaves `vip` empty, the
    second pass does the opposite.  If `start_date` is omitted it defaults to
    today; callers may provide a date immediately following the last entry of
    an existing schedule so that new entries are appended sequentially.
    """
    from datetime import date, timedelta

    if not leaders:
        return []

    if start_date is None:
        start_date = date.today()

    schedule = []
    n = len(leaders)

    # first pass: conductors
    for idx, leader in enumerate(leaders):
        name = leader['name'] if isinstance(leader, dict) else leader
        entry_date = start_date + timedelta(days=idx * interval_days)
        schedule.append({
            "date": entry_date.isoformat(),
            "conductor": name,
            "vip": "",
        })

    # second pass: VIPs
    for idx, leader in enumerate(leaders):
        name = leader['name'] if isinstance(leader, dict) else leader
        entry_date = start_date + timedelta(days=(n + idx) * interval_days)
        schedule.append({
            "date": entry_date.isoformat(),
            "conductor": "",
            "vip": name,
        })

    return schedule


def generate_next_block(leaders, existing_schedule, interval_days: int = 1):
    """Return the next block of entries to append to an existing schedule.

    Always generates a full set of conductors and vips.
    Dates begin one interval after the last existing entry, or today if empty.
    """
    from datetime import date, timedelta, datetime

    if not leaders:
        return []

    # determine start date
    start_date = None
    if existing_schedule:
        last_date = datetime.fromisoformat(existing_schedule[-1]["date"]).date()
        start_date = last_date + timedelta(days=interval_days)

    # generate full conductor+VIP cycle
    entries = generate_schedule(leaders, start_date=start_date, interval_days=interval_days)

    # If there are queued names, fill the open slots (vip in first pass, conductor in second)
    try:
        queue = load_queue()
    except Exception:
        queue = []

    if queue:
        # iterate entries in order and fill any empty slot with the next queued name
        for entry in entries:
            if queue and (not entry.get('vip')):
                entry['vip'] = queue.pop(0)
            if queue and (not entry.get('conductor')):
                entry['conductor'] = queue.pop(0)

    # persist the queue after consuming names
    save_queue(queue)

    return entries



def update_schedule_from_queue():
    """Fill empty VIP and Conductor slots in the schedule from the queue.
    
    Returns the number of slots filled.
    """
    schedule = load_schedule()
    queue = load_queue()
    
    if not schedule:
        return 0
    
    filled_count = 0
    
    # iterate through schedule entries and fill empty slots from queue
    for entry in schedule:
        # fill VIP slot if empty and queue has names
        if queue and not entry.get('vip'):
            entry['vip'] = queue.pop(0)
            filled_count += 1
        # fill Conductor slot if empty and queue has names
        if queue and not entry.get('conductor'):
            entry['conductor'] = queue.pop(0)
            filled_count += 1
    
    # save both schedule and queue
    save_schedule(schedule)
    save_queue(queue)
    
    return filled_count


def replace_inactive_leaders_from_today():
    """Replace inactive leaders in schedule entries from today forward.

    User selects replacements from active leaders list.
    Returns number of role replacements applied.
    """
    from datetime import date

    leaders = load_leaders()
    if not leaders:
        print("No leaders found.")
        return 0

    inactive_names = {
        l.get('name', '').strip()
        for l in leaders
        if isinstance(l, dict) and l.get('name', '').strip() and l.get('status', 'active') != 'active'
    }
    active_names = [
        l.get('name', '').strip()
        for l in leaders
        if isinstance(l, dict) and l.get('name', '').strip() and l.get('status', 'active') == 'active'
    ]

    if not inactive_names:
        print("No inactive leaders found.")
        return 0

    if not active_names:
        print("No active leaders available for replacement.")
        return 0

    schedule = load_schedule()
    if not schedule:
        print("No schedule found.")
        return 0

    today_iso = date.today().isoformat()
    future_entries = [e for e in schedule if e.get('date', '') >= today_iso]
    if not future_entries:
        print("No current/future schedule entries found.")
        return 0

    inactive_in_schedule = set()
    for entry in future_entries:
        conductor = entry.get('conductor', '')
        vip = entry.get('vip', '')
        if conductor in inactive_names:
            inactive_in_schedule.add(conductor)
        if vip in inactive_names:
            inactive_in_schedule.add(vip)

    if not inactive_in_schedule:
        print("No inactive leaders found in schedule from today forward.")
        return 0

    replacement_map = {}
    print(c("Inactive leaders on current/future schedule:", "1;36"))
    for idx, name in enumerate(sorted(inactive_in_schedule), start=1):
        print(f"  {idx}. {name}")

    for old_name in sorted(inactive_in_schedule):
        print("\n")
        print(c(f"Replace '{old_name}' with:", "1;36"))
        for idx, name in enumerate(active_names, start=1):
            print(f"  {idx}. {name}")
        sel = input("Select replacement number (or blank to skip): ").strip()
        if not sel:
            continue
        if sel.isdigit():
            i = int(sel) - 1
            if 0 <= i < len(active_names):
                replacement_map[old_name] = active_names[i]
            else:
                print("Invalid selection; skipped.")
        else:
            print("Invalid input; skipped.")

    if not replacement_map:
        print("No replacements selected.")
        return 0

    replacements_applied = 0
    for entry in schedule:
        if entry.get('date', '') < today_iso:
            continue
        for role in ('conductor', 'vip'):
            current_name = entry.get(role, '')
            if current_name in replacement_map:
                entry[role] = replacement_map[current_name]
                replacements_applied += 1

    if replacements_applied > 0:
        save_schedule(schedule)

    print("\n")
    print(c("Replacement summary:", "1;36"))
    for old_name, new_name in replacement_map.items():
        print(f"  {old_name} -> {new_name}")
    print(f"Updated {replacements_applied} schedule slot(s).")
    return replacements_applied


def schedule_menu():
    while True:
        header("Train Schedule Menu")
        print("1.) Show")
        print("2.) Queue")
        print("3.) Update")
        print("4.) History")
        print("5.) Generate")
        print("6.) Randomize")
        print("7.) Replace Inactive")
        print("8.) Back")
        print("\n")
        choice = input("Select an option: ")

        if choice == '1':
            clear()
            schedule = load_schedule()
            print(c("Current Schedule:", "1;36"))
            if not schedule:
                print("  (no schedule generated yet)")
            else:
                print("1.) Full Schedule")
                print("2.) Current Week (Sunday-Saturday)")
                print("\n")
                view_choice = input("Select view: ").strip()

                from datetime import date, timedelta
                filtered = []
                show_weekday = False

                if view_choice == '1':
                    filtered = schedule
                elif view_choice == '2':
                    show_weekday = True
                    today = date.today()
                    # Python weekday: Monday=0..Sunday=6; convert to Sunday-based week start.
                    days_since_sunday = (today.weekday() + 1) % 7
                    week_start = today - timedelta(days=days_since_sunday)
                    week_end = week_start + timedelta(days=6)
                    start_iso = week_start.isoformat()
                    end_iso = week_end.isoformat()
                    filtered = [entry for entry in schedule if start_iso <= entry['date'] <= end_iso]
                    print("\n")
                    print(c(f"Week: {start_iso} to {end_iso}", "1;36"))
                else:
                    print("Invalid selection.")
                    input("\nPress Enter to continue...")
                    continue

                if not filtered:
                    print("  (no schedule entries for this view)")
                else:
                    for idx, entry in enumerate(filtered, start=1):
                        entry_date = entry.get('date', '')
                        if show_weekday:
                            try:
                                day_name = date.fromisoformat(entry_date).strftime("%A")
                                print(f"  {idx}. {day_name} {entry_date}")
                            except ValueError:
                                print(f"  {idx}. {entry_date}")
                        else:
                            print(f"  {idx}. {entry_date}")
                        print(f"      {c('Conductor: ', '1;32')}{entry.get('conductor','')}")
                        print(f"      {c('VIP: ', '1;33')}{entry.get('vip','')}")
            input("\nPress Enter to continue...")
        elif choice == '2':
            # Queue submenu: view, add, delete queued members
            clear()
            while True:
                queue = load_queue()
                print(c("Queue Menu", "1;36"))
                print("Current queue:")
                if not queue:
                    print("  (queue is empty)")
                else:
                    for idx, name in enumerate(queue, start=1):
                        print(f"  {idx}. {name}")
                print("\nOptions: 1) Add  2) Delete  3) Back")
                print("\n")
                sub = input("Select an option: ").strip()
                if sub == '1':
                    name = input("Enter name to add to queue: ").strip()
                    if name:
                        queue.append(name)
                        save_queue(queue)
                        print(f"Added '{name}' to queue.")
                    else:
                        print("No name entered.")
                    time.sleep(1)
                    clear()
                    continue
                elif sub == '2':
                    if not queue:
                        print("Queue is empty.")
                        time.sleep(1)
                        clear()
                        continue
                    for idx, name in enumerate(queue, start=1):
                        print(f"  {idx}. {name}")
                    sel = input("Enter number to remove (or blank to cancel): ").strip()
                    if sel.isdigit():
                        i = int(sel) - 1
                        if 0 <= i < len(queue):
                            removed = queue.pop(i)
                            save_queue(queue)
                            print(f"Removed '{removed}' from queue.")
                        else:
                            print("Invalid index.")
                    else:
                        print("Canceled.")
                    time.sleep(1)
                    clear()
                    continue
                else:
                    break
            clear()
        elif choice == '3':
            # Update schedule from queue
            clear()
            filled = update_schedule_from_queue()
            if filled > 0:
                print(c(f"Updated schedule! Filled {filled} slot(s) from queue.", "1;36"))
                # show the updated schedule
                schedule = load_schedule()
                print(c("Updated Schedule:", "1;36"))
                from datetime import date
                today = date.today().isoformat()
                # filter to show only today and forward
                filtered = [entry for entry in schedule if entry['date'] >= today]
                if not filtered:
                    print("  (no upcoming schedule entries)")
                else:
                    for idx, entry in enumerate(filtered, start=1):
                        print(f"  {idx}. {entry['date']}")
                        print(f"      {c('Conductor: ', '1;32')}{entry.get('conductor','')}")
                        print(f"      {c('VIP: ', '1;33')}{entry.get('vip','')}")
            else:
                print("No slots were filled (schedule empty or queue empty).")
            input("\nPress Enter to continue...")
        elif choice == '4':
            # History - show name-based conductor and vip counts with search
            clear()
            search_name = input("Search train history (leave blank to show all): ").strip()
            history = load_train_history()
            clear()
            
            if not history:
                print(c("Train History:", "1;36"))
                print("  (no history recorded)")
            else:
                # filter based on search
                if search_name:
                    from difflib import get_close_matches
                    history_names = list(history.keys())
                    search_lower = search_name.lower()
                    
                    # first try prefix/starts with match
                    prefix_matches = [name for name in history_names if name.lower().startswith(search_lower)]
                    
                    if prefix_matches:
                        matches = prefix_matches
                    else:
                        # fall back to fuzzy matching with lower cutoff
                        matches = get_close_matches(search_name, history_names, n=5, cutoff=0.3)
                    
                    if not matches:
                        print(f"No history found matching '{search_name}'.")
                    else:
                        print(c("Train History:", "1;36"))
                        # sort matches by total count descending
                        sorted_matches = sorted(matches, key=lambda x: history[x]['conductor_count'] + history[x]['vip_count'], reverse=True)
                        for name in sorted_matches:
                            counts = history[name]
                            print(f"  {name}")
                            print(f"      {c('Conductor: ', '1;32')}{counts['conductor_count']}")
                            print(f"      {c('VIP: ', '1;33')}{counts['vip_count']}")
                            print(f"      {c('Total: ', '1;36')}{counts['conductor_count'] + counts['vip_count']}")
                else:
                    # show all
                    print(c("Train History:", "1;36"))
                    # sort by total count (conductor + vip) descending
                    sorted_history = sorted(history.items(), key=lambda x: x[1]['conductor_count'] + x[1]['vip_count'], reverse=True)
                    for name, counts in sorted_history:
                        print(f"  {name}")
                        print(f"      {c('Conductor: ', '1;32')}{counts['conductor_count']}")
                        print(f"      {c('VIP: ', '1;33')}{counts['vip_count']}")
                        print(f"      {c('Total: ', '1;36')}{counts['conductor_count'] + counts['vip_count']}")
            input("\nPress Enter to continue...")
        elif choice == '5':
            # Generate (use only active leaders)
            leaders = load_leaders()
            clear()
            active_leaders = [l for l in leaders if l.get('status', 'active') == 'active']
            if not active_leaders:
                print("No active leaders defined; cannot generate schedule.")
                input("\nPress Enter to continue...")
            else:
                existing = load_schedule()
                interval = 1
                new_entries = generate_next_block(active_leaders, existing, interval_days=interval)
                schedule = existing + new_entries
                save_schedule(schedule)
                print(c(f"Schedule generated (Conductor & VIP block)!", "1;36"))
                for idx, entry in enumerate(new_entries, start=len(existing) + 1):
                    print(f"  {idx}. {entry['date']}")
                    print(f"      {c('Conductor: ', '1;32')}{entry.get('conductor','')}")
                    print(f"      {c('VIP: ', '1;33')}{entry.get('vip','')}")
                input("\nPress Enter to continue...")
        elif choice == '6':
            clear()
            print(c("Randomize Source", "1;36"))
            print("1.) Leaders")
            print("2.) Train History")
            print("3.) Cancel")
            source_choice = input("Select source: ").strip()

            if source_choice == '1':
                leaders = load_leaders()
                pool = [l.get('name', '').strip() for l in leaders if isinstance(l, dict) and l.get('name', '').strip()]
                source_label = "leaders"
            elif source_choice == '2':
                history = load_train_history()
                pool = [name.strip() for name in history.keys() if isinstance(name, str) and name.strip()]
                source_label = "train history"
            else:
                continue

            if not pool:
                print(f"No names found in {source_label}.")
                input("\nPress Enter to continue...")
                continue

            count_raw = input(f"How many random names to pull? (1-{len(pool)}): ").strip()
            if not count_raw.isdigit():
                print("Invalid number.")
                input("\nPress Enter to continue...")
                continue

            count = int(count_raw)
            if count < 1 or count > len(pool):
                print(f"Please enter a number between 1 and {len(pool)}.")
                input("\nPress Enter to continue...")
                continue

            picks = random.sample(pool, count)
            clear()
            print(c(f"Random names from {source_label}:", "1;36"))
            for idx, name in enumerate(picks, start=1):
                print(f"  {idx}. {name}")
            input("\nPress Enter to continue...")
        elif choice == '7':
            clear()
            replace_inactive_leaders_from_today()
            input("\nPress Enter to continue...")
        elif choice == '8':
            return

if __name__ == "__main__":
    main_menu()
