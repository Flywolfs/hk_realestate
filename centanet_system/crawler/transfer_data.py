import os
import json

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
        if type == "buy" :
            transaction = {
                "unit_location": item["estateName"] + " " + item["buildingName"] + " " + item["yAxis"] + " " + item["xAxis"],
                "date": item["regDate"].split("T")[0] if "regDate" in item else None,
                "total_price": item["transactionPrice"] if "transactionPrice" in item else None,
                "room_count": item["bedroomCount"] if "bedroomCount" in item else None,
                "area": item["nArea"] if "nArea" in item else None,
                "price_per_sqft": item["nUnitPrice"] if "nUnitPrice" in item else None,
                "profit_loss_rate": item["gainPercent"] if "gainPercent" in item else None
            }
        if type == "rent":
            transaction = {
                "unit_location": item["estateName"] + " " + item["buildingName"] + " " + item["yAxis"] + " " + item["xAxis"],
                "date": item["insDate"].split("T")[0] if "insDate" in item else None,
                "total_price": item["transactionPrice"] if "transactionPrice" in item else None,
                "area": item["nArea"] if "nArea" in item else None,
                "rent_per_sqft":  round(item["transactionPrice"]/item["nArea"],1) if "nArea" in item and "transactionPrice" in item else None
            }
        new_data["transactions"].append(transaction)
    with open(output_file, 'w') as f:
        json.dump(new_data, f, indent=1, ensure_ascii=False)

if __name__ == "__main__":
    input_path = "transaction_record_20260223/rent"
    output_path = "transaction_record_20260223_trans/rent"
    # 创建目标目录
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # 遍历
    for filename in os.listdir(input_path):
        input_file = os.path.join(input_path, filename)
        output_file = os.path.join(output_path, filename)
        transfer_data(input_file, output_file, type="rent")  
