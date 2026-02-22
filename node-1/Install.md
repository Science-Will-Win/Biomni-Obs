.env 파일을 생성한 뒤 아래 명령어 실행
chmod +x setup_node1.sh
./setup_node1.sh

설치 및 빌드가 완료되면 서버의 8000번 포트로 설치가 정상적으로 이루어졌는지 확인
http://<IP주소>:8000/docs 로 들어갔을 때 swagger UI가 보이면 정상적으로 완료된 것

UI 띄우기 위해 아래 명령어 실행
cd Biomni-Web/frontend/
npm run dev -- --host