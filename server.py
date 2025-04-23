from mcp.server.fastmcp import FastMCP
import datetime
 
mcp = FastMCP("Test Server")
 

@mcp.tool()
def get_time() -> str:
    """获取当前系统时间"""
    return str(datetime.datetime.now())

@mcp.tool()
def calculate_bmi(weight_kg: float, height_m: float) -> float:
    """根据体重（kg）和身高（m）计算BMI"""
    return weight_kg / (height_m ** 2)
 
 
if __name__ == "__main__":
    # print('server start ...')
    mcp.run(transport='stdio')