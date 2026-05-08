FROM jiyeonl/biomni-base:latest

WORKDIR /app/backend_code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# [추가] 최종 이미지에서 otel bootstrap 재실행
# (base 이미지 빌드 후 requirements.txt에 패키지가 추가될 수 있으므로)
RUN opentelemetry-bootstrap -a install

COPY . /app/backend_code

# CRLF 제거 및 실행 권한 부여
RUN tr -d '\r' < entrypoint.sh > entrypoint_tmp.sh \
    && mv entrypoint_tmp.sh entrypoint.sh \
    && chmod +x entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/backend_code/entrypoint.sh"]
