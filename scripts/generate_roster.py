"""生成多航司机组名册。添加国航/南航/东航/海航/首都航/深航等。"""
import json, os, random

random.seed(2024)

# ========== 航司及基地定义 ==========
AIRLINE_DEFS = {
    '四川航空': {
        'full_name': '四川航空股份有限公司',
        'bases': ['成都', '重庆', '昆明', '宜宾', '绵阳', '杭州'],
    },
    '中国国际航空': {
        'full_name': '中国国际航空股份有限公司',
        'bases': ['北京', '成都', '上海', '杭州', '天津', '重庆'],
    },
    '中国南方航空': {
        'full_name': '中国南方航空股份有限公司',
        'bases': ['广州', '深圳', '北京', '乌鲁木齐', '武汉', '沈阳', '三亚'],
    },
    '中国东方航空': {
        'full_name': '中国东方航空股份有限公司',
        'bases': ['上海', '昆明', '西安', '北京', '南京', '武汉', '青岛'],
    },
    '海南航空': {
        'full_name': '海南航空股份有限公司',
        'bases': ['海口', '北京', '三亚', '西安', '深圳', '广州'],
    },
    '首都航空': {
        'full_name': '北京首都航空有限公司',
        'bases': ['北京', '杭州', '三亚', '丽江'],
    },
    '深圳航空': {
        'full_name': '深圳航空有限责任公司',
        'bases': ['深圳', '广州', '南京', '西安', '沈阳'],
    },
    '厦门航空': {
        'full_name': '厦门航空有限公司',
        'bases': ['厦门', '福州', '杭州', '长沙', '北京'],
    },
}

# ========== 姓名生成 ==========
SURNAMES = [
    '李','王','张','刘','陈','杨','赵','黄','周','吴',
    '徐','孙','马','朱','胡','郭','何','林','罗','高',
    '梁','宋','郑','谢','韩','冯','于','董','萧','程',
    '曹','袁','邓','许','傅','沈','曾','彭','吕','苏',
    '卢','蒋','蔡','贾','丁','魏','薛','叶','阎','余',
    '潘','杜','戴','夏','钟','汪','田','任','姜','范',
    '方','石','姚','谭','廖','邹','熊','金','陆','郝',
    '孔','白','崔','康','毛','邱','秦','江','史','顾',
    '侯','邵','孟','龙','万','段','雷','钱','汤','尹',
    '易','常','武','乔','贺','赖','龚','文','庞','樊',
]
MALE_GIVEN = [
    '伟','强','磊','洋','飞','文','明','华','平','刚',
    '军','勇','杰','斌','宇','志','建','国','辉','峰',
    '海','涛','鹏','龙','宏','宁','亮','林','浩','博',
    '锐','俊','鑫','天','泽','昊','嘉','恒','毅','远',
]
FEMALE_GIVEN = [
    '芳','娜','敏','静','丽','秀','英','娟','萍','婷',
    '琴','霞','雪','琳','玲','华','红','梅','兰','燕',
    '慧','洁','怡','媛','思','欣','瑶','蕾','倩','柳',
    '芸','薇','莹','璇','月','晶','颖','露','彤','涵',
]

def gen_name(gender):
    pool = MALE_GIVEN if gender == 'm' else FEMALE_GIVEN
    return random.choice(SURNAMES) + random.choice(pool)

def gen_crew(base_size):
    """按基地规模生成人员: (机长数, 副驾数, 乘务长数, 乘务员数)"""
    # 主基地人多，小基地人少
    return {
        'captains': [gen_name('m') for _ in range(base_size)],
        'first_officers': [gen_name('m') for _ in range(base_size)],
        'pursers': [gen_name('f') for _ in range(base_size)],
        'attendants': [gen_name('f') for _ in range(base_size * 2)],
    }

# ========== 生成名册 ==========
all_names = set()

def dedup_names(bases_dict):
    """确保所有姓名不重复"""
    global all_names
    for role_list in bases_dict.values():
        names = []
        for n in role_list:
            while n in all_names:
                # 换姓
                parts = [random.choice(SURNAMES), n[1:]]
                n = ''.join(parts) if len(n) <= 2 else parts[0] + n[len(parts[0]):]
            names.append(n)
            all_names.add(n)
        role_list[:] = names

roster = {'airlines': {}}

for airline, info in AIRLINE_DEFS.items():
    bases_data = {}
    for i, base in enumerate(info['bases']):
        size = 6 - min(3, i)  # 第一个基地6人、第二个5人、第三个4人、之后3人
        bases_data[base] = gen_crew(size)
        for roles in bases_data[base].values():
            dedup_names({'': roles})  # trick: reuse dedup
    
    roster['airlines'][airline] = {
        'full_name': info['full_name'],
        'bases': {b: {k: list(v) for k, v in d.items()} for b, d in bases_data.items()},
    }

roster['qualifications'] = {
    'captains': ['A319', 'A320', 'A330', 'B737', 'B787'],
    'first_officers': ['A319', 'A320', 'A330', 'B737', 'B787'],
    'pursers': ['A319', 'A320'],
    'attendants': ['A319', 'A320', 'A330', 'B737'],
}
roster['limits'] = {
    'max_daily_hours': 8,
    'max_duty_hours': 14,
}

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(PROJECT_DIR, 'backend', 'data', 'crew_roster.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(roster, f, ensure_ascii=False, indent=2)

# 统计
total = 0
for a, info in roster['airlines'].items():
    bases = info['bases']
    for b, roles in bases.items():
        n = sum(len(v) for v in roles.values())
        total += n
        print(f'  {a}/{b}: {len(roles["captains"])}cap {len(roles["first_officers"])}off {len(roles["pursers"])}pur {len(roles["attendants"])}att = {n}人')
    print(f'{a}: {len(bases)} 基地')

print(f'\n总计 {total} 人, {len(roster["airlines"])} 航司')
print(f'Saved to {out}')
