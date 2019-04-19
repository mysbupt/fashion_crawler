import os
import simplejson as json


def get_loc_by_admin2():
    if os.path.exists("./all_loc_info_by_admin.json"):
        return json.load(open("./all_loc_info_by_admin.json"))

    data = json.load(open("./all_loc_info.json"))

    result = {}
    for k, v in data.items():
        cc = v["parse_cc"]
        admin1 = v["parse_admin1"]
        admin2 = v["parse_admin2"]
        loc = v["parse_loc_name"]

        cc_map = {"SG": "Singapore", "HK": "Hong Kong"}
        if cc in ["SG", "HK"]:
            cc = cc_map[cc]
            if cc not in result:
                result[cc] = {k: v}
            else:
                result[cc][k] = v
        else:
            if admin1 not in result: 
                result[admin1] = {k: v}
            else:
                result[admin1][k] = v

            if admin2 not in result: 
                result[admin2] = {k: v}
            else:
                result[admin2][k] = v

    json.dump(result, open("./all_loc_info_by_admin.json", "w"))
    return result


def main():
    admin_loc = get_loc_by_admin2()

    city_list = json.load(open("city_info.json")).keys()
    for city in city_list:
        print(city, len(admin_loc[city]))


if __name__ == "__main__":
    main()
