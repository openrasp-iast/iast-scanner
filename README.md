# IAST-SCANNER

IAST插桩式主动扫描器

## 运行条件

* OpenRASP 管理后台 版本 >= 1.2.0，并至少有一台在线主机
* Python 3.6 或者更高版本
* MySQL 5.5.3， 或者更高版本

## 运行
```bash
# 查看云控后天，添加主机文档：http://localhost:5173/host
```

## 架构图

![architecture.png](doc%2Fimg%2Farchitecture.png)

### MySQL

配置 MySQL 数据库，建立名为 openrasp 的数据库，并为 rasp@% 授权，密码为 rasp123（建议使用强度更高的密码，这里只是举例）。请用
root 账号连接 mysql 并执行如下语句:

```sql
-- 如果是 MySQL 8.X 以及更高版本
DROP DATABASE IF EXISTS openrasp;
CREATE DATABASE openrasp default charset utf8mb4 COLLATE utf8mb4_general_ci;
CREATE user 'rasp'@'%' identified with mysql_native_password by 'rasp123';
grant all privileges on openrasp.* to 'rasp'@'%' with grant option;
-- OR
grant all privileges on openrasp.* to 'rasp'@'localhost' with grant option;
FLUSH PRIVILEGES;

-- 如果是低版本 MySQL
DROP DATABASE IF EXISTS openrasp;
CREATE DATABASE openrasp default charset utf8mb4 COLLATE utf8mb4_general_ci;
grant all privileges on openrasp.* to 'rasp'@'%' identified by 'rasp123';
-- OR
grant all privileges on openrasp.* to 'rasp'@'localhost' identified by 'rasp123';
FLUSH PRIVILEGES;
```
