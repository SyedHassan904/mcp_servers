from dotenv import load_dotenv
load_dotenv()
from fastmcp import Client
import os
from fastmcp.server import create_proxy
from fastmcp.client.auth import BearerAuth


client = Client(
    "https://normal-gray-dinosaur.fastmcp.app/mcp",
    auth=BearerAuth(os.getenv("auth_token"))
)

mcp = create_proxy(
    client,
    name="Proxy Server"
    )

# @mcp.tool
# def roll_dice(n_dice:int):
#     """roll the n number of dices n=n_dice"""
#     return [random.randint(1,6) for _ in range(n_dice)]

# @mcp.tool
# def add_nums(first_num:float,second_num:float)->float:
#     """add two numbers"""
#     return first_num+second_num


if __name__ == "__main__":
    mcp.run()