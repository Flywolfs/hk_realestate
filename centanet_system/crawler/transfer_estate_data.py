import os
import json

def transfer_data(input_file, output_file):
    with open(input_file, 'r') as f:
        data = json.load(f)
    new_data = {
        
    }
    for item in data["data"]:
        new_data[item["typeCode"]] = {
            "name": item.get("estateName",""),
            "id": item.get("typeCode",""),
            "address": item.get("address",""),
            "coordinates": {
                "latitude": item.get("gMap", {}).get("lat", 0.0),
                "longitude": item.get("gMap", {}).get("lng", 0.0)
            },
            "basic_info": {
                "building_count": item.get("buildingCount", 0),
                "establish_year": int(item.get("minOpDate", "0000-00-00").split("-")[0]),
                "developer": item.get("developer", ""),
                "management_company": item.get("managementCompany", ""),
                "units": item.get("unitCount", 0),
                "primary_school": int(item.get("schoolNet", {}).get("primarySchoolNetwork", 0)),
                "middle_school": item.get("schoolNet", {}).get("secondarySchoolScope", {}).get("db","")+"("+item.get("schoolNet", {}).get("secondarySchoolScope", {}).get("scp_mkt","")+item.get("schoolNet", {}).get("secondarySchoolScope", {}).get("db_code","")+")"
            }
        }
    with open(output_file, 'w') as f:
        json.dump(new_data, f, indent=1, ensure_ascii=False)

if __name__ == "__main__":
    input_path = "/home/zhangchi/Documents/28hse/centanet_system/crawler/estate_info_20260221.json"
    output_path = "/home/zhangchi/Documents/28hse/centanet_system/crawler/estate_info_20260221_convert.json"
    transfer_data(input_path, output_path)  
