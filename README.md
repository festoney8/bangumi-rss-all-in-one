# bangumi-rss-all-in-one

## 功能

- 将多个动漫发布站的RSS合并为一个文件，配合Nginx搭建个人RSS聚合，可多人共用

- 支持多数动漫发布站 (dmhy/acgnx/kisssub/mikan/ncraw/nyaa/acgrip/bangumimoe)

## 运行环境

0. 部署机器需对目标站点网络可达
1. Python >= 3.7
2. Nginx 或 Apache 等网页服务器

## 运行

1. 启用nginx

2. clone项目，运行 `pip install -r requirements.txt` 安装第三方库

3. 在 `config.yaml` 文件中根据个人需求调整站点设置

    注意配置中`xml_abspath`应设置为nginx网页路径 (如 `/var/www/html` )

4. 测试运行 `python3 test.py`

   观察日志输出有无Error，有无站点无法连接的情况，并适当调整配置

   查看nginx网页路径下是否有xml文件生成

   查看通过URL是否可访问xml文件

5. 编写 `systemd` 服务

    ```bash
    # 进入service目录
    cd /etc/systemd/system/
    # 新增service
    nano bangumi-rss.service
    ```

    配置样例，需修改 `main.py` 的绝对路径：

    ```
    [Unit]
    Description=Bangumi rss all-in-one service
    After=multi-user.target
    [Service]
    Type=simple
    Restart=always
    ExecStart=/usr/bin/python3 /<path>/main.py
    [Install]
    WantedBy=multi-user.target
    ```

    ```bash
    # 加载服务文件
    systemctl daemon-reload
    # 启用服务
    systemctl start bangumi-rss
    # 设置开机自启动
    systemctl enable bangumi-rss
    # 查看服务状态
    systemctl status bangumi-rss
    ```

6. 如果懒得配置 `systemd`，可以开一个 `screen` 运行 `python3 main.py`

## 注意

- 刷新间隔不可过低，部分站点会封禁频繁访问的IP