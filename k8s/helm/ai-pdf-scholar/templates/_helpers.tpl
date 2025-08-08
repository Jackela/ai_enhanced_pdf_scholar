{{/*
Expand the name of the chart.
*/}}
{{- define "ai-pdf-scholar.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "ai-pdf-scholar.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ai-pdf-scholar.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ai-pdf-scholar.labels" -}}
helm.sh/chart: {{ include "ai-pdf-scholar.chart" . }}
{{ include "ai-pdf-scholar.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "ai-pdf-scholar.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ai-pdf-scholar.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Backend selector labels
*/}}
{{- define "ai-pdf-scholar.backend.selectorLabels" -}}
{{ include "ai-pdf-scholar.selectorLabels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Frontend selector labels
*/}}
{{- define "ai-pdf-scholar.frontend.selectorLabels" -}}
{{ include "ai-pdf-scholar.selectorLabels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
Nginx selector labels
*/}}
{{- define "ai-pdf-scholar.nginx.selectorLabels" -}}
{{ include "ai-pdf-scholar.selectorLabels" . }}
app.kubernetes.io/component: nginx
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "ai-pdf-scholar.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "ai-pdf-scholar.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create a default fully qualified postgresql name.
*/}}
{{- define "ai-pdf-scholar.postgresql.fullname" -}}
{{- printf "%s-%s" .Release.Name "postgresql" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified redis name.
*/}}
{{- define "ai-pdf-scholar.redis.fullname" -}}
{{- printf "%s-%s" .Release.Name "redis-master" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified elasticsearch name.
*/}}
{{- define "ai-pdf-scholar.elasticsearch.fullname" -}}
{{- printf "%s-%s" .Release.Name "elasticsearch-master" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Get the password secret.
*/}}
{{- define "ai-pdf-scholar.secretName" -}}
{{- printf "%s-secrets" (include "ai-pdf-scholar.fullname" .) }}
{{- end }}

{{/*
Get the configuration configmap.
*/}}
{{- define "ai-pdf-scholar.configmapName" -}}
{{- printf "%s-config" (include "ai-pdf-scholar.fullname" .) }}
{{- end }}

{{/*
Backend image
*/}}
{{- define "ai-pdf-scholar.backend.image" -}}
{{- $registryName := .Values.global.imageRegistry | default .Values.image.registry -}}
{{- $repositoryName := .Values.backend.image.repository -}}
{{- $tag := .Values.backend.image.tag | default .Chart.AppVersion -}}
{{- if $registryName }}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- else }}
{{- printf "%s:%s" $repositoryName $tag -}}
{{- end }}
{{- end }}

{{/*
Frontend image
*/}}
{{- define "ai-pdf-scholar.frontend.image" -}}
{{- $registryName := .Values.global.imageRegistry | default .Values.image.registry -}}
{{- $repositoryName := .Values.frontend.image.repository -}}
{{- $tag := .Values.frontend.image.tag | default .Chart.AppVersion -}}
{{- if $registryName }}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- else }}
{{- printf "%s:%s" $repositoryName $tag -}}
{{- end }}
{{- end }}

{{/*
Nginx image
*/}}
{{- define "ai-pdf-scholar.nginx.image" -}}
{{- $registryName := .Values.global.imageRegistry | default .Values.image.registry -}}
{{- $repositoryName := .Values.nginx.image.repository -}}
{{- $tag := .Values.nginx.image.tag -}}
{{- if $registryName }}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- else }}
{{- printf "%s:%s" $repositoryName $tag -}}
{{- end }}
{{- end }}

{{/*
Generate database connection string
*/}}
{{- define "ai-pdf-scholar.database.connectionString" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "postgresql://%s:%s@%s:5432/%s" .Values.postgresql.auth.username .Values.postgresql.auth.password (include "ai-pdf-scholar.postgresql.fullname" .) .Values.postgresql.auth.database }}
{{- else }}
{{- printf "postgresql://%s:%s@%s:%d/%s" .Values.externalDatabase.user .Values.externalDatabase.password .Values.externalDatabase.host (.Values.externalDatabase.port | int) .Values.externalDatabase.database }}
{{- end }}
{{- end }}

{{/*
Generate redis connection string
*/}}
{{- define "ai-pdf-scholar.redis.connectionString" -}}
{{- if .Values.redis.enabled }}
{{- printf "redis://%s:6379/0" (include "ai-pdf-scholar.redis.fullname" .) }}
{{- else }}
{{- printf "redis://%s:%d/0" .Values.externalRedis.host (.Values.externalRedis.port | int) }}
{{- end }}
{{- end }}

{{/*
Generate elasticsearch connection string
*/}}
{{- define "ai-pdf-scholar.elasticsearch.connectionString" -}}
{{- if .Values.elasticsearch.enabled }}
{{- printf "http://%s:9200" (include "ai-pdf-scholar.elasticsearch.fullname" .) }}
{{- else }}
{{- printf "http://%s:%d" .Values.externalElasticsearch.host (.Values.externalElasticsearch.port | int) }}
{{- end }}
{{- end }}