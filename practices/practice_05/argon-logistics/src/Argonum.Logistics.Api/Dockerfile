# Контекст сборки: корень проекта (argon-logistics/), см. docker-compose.yml
FROM mcr.microsoft.com/dotnet/sdk:10.0-alpine AS build
WORKDIR /src
COPY src/Argonum.Logistics.Core/Argonum.Logistics.Core.csproj src/Argonum.Logistics.Core/
COPY src/Argonum.Logistics.Api/Argonum.Logistics.Api.csproj src/Argonum.Logistics.Api/
RUN dotnet restore src/Argonum.Logistics.Api
COPY src src
RUN dotnet publish src/Argonum.Logistics.Api -c Release -o /app --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0-alpine AS runtime
WORKDIR /app
# /data под SQLite: каталог принадлежит непривилегированному пользователю, том наследует владельца
RUN mkdir /data && chown app /data
COPY --from=build /app .
USER app
ENV ASPNETCORE_URLS=http://+:8080 \
    ConnectionStrings__Argon="Data Source=/data/argon.db"
EXPOSE 8080
ENTRYPOINT ["dotnet", "Argonum.Logistics.Api.dll"]
