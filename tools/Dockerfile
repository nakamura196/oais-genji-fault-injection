# CI（release.yml の DIP 段）と同じ道具をそろえた検査用の環境
FROM eclipse-temurin:21-jdk-noble
RUN apt-get update && apt-get install -y --no-install-recommends p7zip-full unzip zsh zip perl python3 python3-pip python3-venv curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /venv && /venv/bin/pip install --no-cache-dir bagit==1.9.0 lxml==6.1.3 beautifulsoup4==4.15.0 requests==2.32.5 tqdm==4.70.1 openpyxl==3.1.5 EbookLib==0.20 PyYAML==6.0.3
RUN curl -sfL -o /opt/saxon-he.jar https://repo1.maven.org/maven2/net/sf/saxon/Saxon-HE/12.5/Saxon-HE-12.5.jar && curl -sfL -o /opt/xmlresolver.jar https://repo1.maven.org/maven2/org/xmlresolver/xmlresolver/6.0.4/xmlresolver-6.0.4.jar
ENV PATH=/venv/bin:$PATH SAXON_JAR=/opt/saxon-he.jar:/opt/xmlresolver.jar
WORKDIR /work
