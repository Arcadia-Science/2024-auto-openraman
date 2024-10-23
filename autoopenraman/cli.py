import argparse
import sys


class CLIparse(object):
    def __init__(self) -> None:
        parser = argparse.ArgumentParser(description='AutoOpenRaman acquisition',
                                         usage='''autoopenraman <command> [<args>]''')
        parser.add_argument('command', help='Can be one of: live, acq, plot')

        # parse command
        args = parser.parse_args(sys.argv[1:2])
        if not hasattr(self, args.command):
            print('Command {0} not recognized.'.format(args.command))
            parser.print_help()
            exit(1)
        getattr(self, args.command)()
    
    def live(self):
        print("Live mode")
    def acq(self):
        print("Acquisition mode")
    def plot(self):
        print("Plot mode")

def main():
    CLIparse()

if __name__ == "__main__":
    main()