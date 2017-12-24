# Introduction

See https://xianzhi.aliyun.com/forum/topic/1819/


# Run

```
docker build -t vul-py-server .
docker run -d --name=vul-py -p 127.0.0.1:30000:9080 vul-py-server
```

remove

```
docker rm -f vul-py
```
