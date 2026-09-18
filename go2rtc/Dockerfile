FROM alexxit/go2rtc:latest
COPY go2rtc.yaml.tmpl /app/go2rtc.yaml.tmpl
COPY run.sh /app/run.sh
RUN chmod +x /app/run.sh
ENTRYPOINT ["/app/run.sh"]
