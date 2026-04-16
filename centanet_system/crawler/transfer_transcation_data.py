import os
import json
from datetime import datetime

def transfer_data(input_file, output_file, type="buy"):
    with open(input_file, 'r') as f:
        data = json.load(f)
    new_data = {
        "estate_id": data["typeCode"],
        "record_type": type,
        "total_records": data["count"],
        "transactions": []
    }
    for item in data["data"]:
        date_reg = ""
        date_ins = ""
        if "regDate" in item:
            date_reg = datetime.strptime(item["regDate"].split("T")[0], "%Y-%m-%d")
        if "insDate" in item:
            date_ins = datetime.strptime(item["insDate"].split("T")[0], "%Y-%m-%d")
        #如果同时存在，那么最终日期是date_reg和date_ins中更大的那个
        if date_reg != "" and date_ins != "":
            date = max(date_reg, date_ins)
        elif date_reg != "":
            date = date_reg
        elif date_ins != "":
            date = date_ins
        else:
            date = None
        #date转为str格式，只保留年月日
        date = date.strftime("%Y-%m-%d") if date is not None else None
        if type == "buy" :
            transaction = {
                "unit_location": item["estateName"] + " " + item["buildingName"] + " " + item["yAxis"] + " " + item["xAxis"],
                "date": date,
                "total_price": item["transactionPrice"] if "transactionPrice" in item else None,
                "room_count": item["bedroomCount"] if "bedroomCount" in item else None,
                "area": item["nArea"] if "nArea" in item else None,
                "price_per_sqft": item["nUnitPrice"] if "nUnitPrice" in item else None,
                "profit_loss_rate": item["gainPercent"] if "gainPercent" in item else None
            }
        if type == "rent":
            transaction = {
                "unit_location": item["estateName"] + " " + item["buildingName"] + " " + item["yAxis"] + " " + item["xAxis"],
                "date": date,
                "total_price": item["transactionPrice"] if "transactionPrice" in item else None,
                "area": item["nArea"] if "nArea" in item else None,
                "rent_per_sqft":  round(item["transactionPrice"]/item["nArea"],1) if "nArea" in item and "transactionPrice" in item else None
            }
        new_data["transactions"].append(transaction)
    with open(output_file, 'w') as f:
        json.dump(new_data, f, indent=1, ensure_ascii=False)

if __name__ == "__main__":
    input_path = "transaction_record_20260411/rent"
    output_path = "transaction_record_20260411_trans/rent"
    # 创建目标目录
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # 遍历
    for filename in os.listdir(input_path):
        input_file = os.path.join(input_path, filename)
        output_file = os.path.join(output_path, filename)
        transfer_data(input_file, output_file, type="rent")  
