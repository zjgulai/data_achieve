# Robin（暗网 OSINT）需要一个 Tor SOCKS5 出口。
# 单独起一个 sidecar 比在 api 镜像里塞 tor 更简单：api 只连 socks5h://tor:9050。
FROM alpine:3.20

RUN apk add --no-cache tor \
    && mkdir -p /var/lib/tor \
    && chown -R tor:tor /var/lib/tor

USER tor

EXPOSE 9050

# -f 前台运行，交给 compose 管生命周期
CMD ["tor", "--SocksPort", "0.0.0.0:9050"]
