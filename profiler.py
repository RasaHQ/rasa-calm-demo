import sys

import yappi
from rasa import __main__


def main():
    """Run the Rasa main function with Yappi profiling enabled."""
    yappi.set_clock_type("wall")
    yappi.start()
    sys.argv = ["rasa", "run", "--enable-api"]

    try:
        __main__.main()
    finally:
        yappi.stop()
        func_stats = yappi.get_func_stats()
        file_name = "output.pstat"
        func_stats.save(file_name, type="pstat")
        print(f"Profiling data saved to {file_name}. Run `snakeviz {file_name}`.")


if __name__ == "__main__":
    main()
