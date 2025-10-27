import os

from termcolor import colored
 
def pretty_print_diff(diff_file="results/diff.txt"):

    if not os.path.exists(diff_file):

        print(colored(f"❌ File not found: {diff_file}", "red"))

        return
 
    with open(diff_file, 'r', encoding='utf-8') as f:

        lines = f.readlines()
 
    print(colored("\n🌸 CPI Response Comparison 🌸", "magenta", attrs=["bold"]))

    print(colored("──────────────────────────────────────────────\n", "cyan"))
 
    for line in lines:

        line = line.rstrip("\n")
 
        if line.startswith("---"):

            print(colored("🔹 " + line, "yellow", attrs=["bold"]))

        elif line.startswith("+++"):

            print(colored("🔹 " + line, "yellow", attrs=["bold"]))

        elif line.startswith("@@"):

            print(colored("\n📘 Section → " + line, "blue", attrs=["bold"]))

        elif line.startswith("+"):

            print(colored("🟢 Added:  " + line[1:], "green"))

        elif line.startswith("-"):

            print(colored("🔴 Removed:" + line[1:], "red"))

        else:

            print(colored("   " + line, "white"))
 
    print(colored("\n──────────────────────────────────────────────", "cyan"))

    print(colored("✨ End of comparison ✨\n", "magenta", attrs=["bold"]))
 
 
if __name__ == "__main__":

    pretty_print_diff()

 
