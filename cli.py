# cli.py
import argparse
import requests
import pprint

def get_roaster(args):
    # This function will be called when the 'get' action is triggered
    resp = requests.get(f"http://127.0.0.1:8000/gameweek_roaster?gameweek={args.gameweek}&user_id={args.user_id}")
    pprint.pprint(resp.json())


def main():
    # Create the top-level parser
    parser = argparse.ArgumentParser(description='CLI Tool Example')
    subparsers = parser.add_subparsers(help='Sub-command Help')

    # Create the parser for the "roast" command
    parser_roast = subparsers.add_parser('roaster', help='Roaster operations')
    roast_subparsers = parser_roast.add_subparsers(help='Roaster actions')

    # Create the parser for the "get" command under "roast"
    parser_roast_get = roast_subparsers.add_parser('get', help='Get a roaster')
    parser_roast_get.add_argument('--gameweek', type=int, required=True, help='Game week number')
    parser_roast_get.add_argument('--user-id', type=int, required=True, help='User ID')
    parser_roast_get.set_defaults(func=get_roaster)

    # Parse the arguments
    args = parser.parse_args()
    
    # Call the default function (this part is crucial for triggering the correct action)
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
