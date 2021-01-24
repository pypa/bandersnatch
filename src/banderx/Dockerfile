FROM nginx

# Default config expects bind mount / volume @ /data/pypi/web
RUN mkdir -p /data/pypi/web
RUN mkdir /config
COPY nginx.conf /config

# No HTTPS/TLS in default config - PR welcome
EXPOSE 80
CMD ["nginx", "-c", "/config/nginx.conf"]
