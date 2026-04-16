import { useState, useEffect, useCallback } from 'react';
import { useHistory } from 'react-router-dom';
import { Alert, Button, Card, Input, Select, Space, Typography } from 'antd';
import { ArrowRightOutlined, CopyOutlined, RobotOutlined } from '@ant-design/icons';
import sqlFormatter from 'sql-formatter';

import { useAppContext } from '../../hooks';
import { copyToClipboard } from '../../utils';
import { buildApiUrl } from '../Explore/ExplorePage';
import { Content, Header } from '../components/Ui';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

type CubeMeta = {
  name: string;
  title: string;
  type: 'cube' | 'view';
};

type AIQueryResult = {
  query: any;
  explanation: string;
  sql?: string;
  sqlError?: string;
};

function extractSqlFromResponse(data: any): string | undefined {
  const sqlPayload = Array.isArray(data) ? data[0]?.sql : data?.sql;
  const sqlTuple = sqlPayload?.sql;

  if (Array.isArray(sqlTuple)) {
    return sqlTuple[0];
  }

  if (typeof sqlTuple === 'string') {
    return sqlTuple;
  }

  return undefined;
}

export function AIQueryPage() {
  const { playgroundContext } = useAppContext();
  const { push } = useHistory();

  const { basePath, cubejsToken } = playgroundContext || {};
  const apiUrl = basePath
    ? buildApiUrl(window.location.href.split('#')[0].replace(/\/$/, ''), basePath)
    : '';

  const [cubes, setCubes] = useState<CubeMeta[]>([]);
  const [selectedCubes, setSelectedCubes] = useState<string[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isMetaLoading, setIsMetaLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AIQueryResult | null>(null);

  useEffect(() => {
    if (!apiUrl || !cubejsToken) return;

    setIsMetaLoading(true);
    fetch(`${apiUrl}/meta`, {
      headers: { Authorization: `Bearer ${cubejsToken}` },
    })
      .then((r) => r.json())
      .then((data) => {
        const items: CubeMeta[] = (data.cubes || []).map((c: any) => ({
          name: c.name,
          title: c.title,
          type: c.type || 'cube',
        }));
        setCubes(items);
      })
      .catch(() => {})
      .finally(() => setIsMetaLoading(false));
  }, [apiUrl, cubejsToken]);

  const handleGenerate = useCallback(async () => {
    if (!input.trim() || !apiUrl || !cubejsToken) return;

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${apiUrl}/nl/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${cubejsToken}`,
        },
        body: JSON.stringify({
          naturalLanguage: input.trim(),
          cubeNames: selectedCubes.length > 0 ? selectedCubes : undefined,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.error?.message || 'Failed to generate query');
      }

      const nextResult: AIQueryResult = {
        query: data.query,
        explanation: data.explanation ?? '',
      };

      try {
        const sqlResponse = await fetch(`${apiUrl}/sql`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${cubejsToken}`,
          },
          body: JSON.stringify({
            query: data.query,
          }),
        });

        const sqlData = await sqlResponse.json();

        if (!sqlResponse.ok) {
          throw new Error(sqlData?.error || sqlData?.message || 'Failed to compile SQL');
        }

        const compiledSql = extractSqlFromResponse(sqlData);

        if (!compiledSql) {
          throw new Error('SQL response did not include a SQL query');
        }

        nextResult.sql = sqlFormatter.format(compiledSql);
      } catch (sqlError: any) {
        nextResult.sqlError = sqlError.message;
      }

      setResult(nextResult);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  }, [input, apiUrl, cubejsToken, selectedCubes]);

  const handleOpenInPlayground = () => {
    if (!result) return;
    push(`/build?query=${JSON.stringify(result.query)}`);
  };

  const formattedQuery = result ? JSON.stringify(result.query, null, 2) : '';

  const cubeOptions = cubes.map((c) => ({
    label: `${c.title} (${c.type})`,
    value: c.name,
  }));

  return (
    <>
      <Header>
        <Title level={1} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <RobotOutlined />
          Ask AI
        </Title>
        <Paragraph type="secondary">
          자연어로 질문하면 AI가 Cube.js 쿼리를 생성합니다. 생성된 쿼리는 Playground에서 바로 실행할 수 있습니다.
        </Paragraph>
      </Header>

      <Content>
        <Card style={{ maxWidth: 900 }}>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            {/* Cube/View context selector */}
            <div>
              <Text strong>컨텍스트 설정 (선택)</Text>
              <Paragraph type="secondary" style={{ margin: '4px 0 8px' }}>
                AI가 참조할 큐브/뷰를 선택하세요. 선택하지 않으면 전체 데이터 모델을 사용합니다.
              </Paragraph>
              <Select
                mode="multiple"
                allowClear
                style={{ width: '100%' }}
                placeholder={isMetaLoading ? '큐브 로딩 중...' : '큐브 또는 뷰를 선택하세요'}
                loading={isMetaLoading}
                value={selectedCubes}
                onChange={setSelectedCubes}
                options={cubeOptions}
                optionFilterProp="label"
              />
            </div>

            {/* Natural language input */}
            <div>
              <Text strong>질문 입력</Text>
              <TextArea
                style={{ marginTop: 8 }}
                rows={4}
                placeholder='예: "지난 30일간 국가별 총 매출을 보여줘" 또는 "Show me total revenue by country for the last 30 days"'
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  setError(null);
                  setResult(null);
                }}
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                    void handleGenerate();
                  }
                }}
              />
              <Text type="secondary" style={{ fontSize: 12 }}>
                ⌘ + Enter 로 실행
              </Text>
            </div>

            {/* Generate button */}
            <Button
              type="primary"
              size="large"
              icon={<RobotOutlined />}
              loading={isLoading}
              disabled={!input.trim() || isLoading}
              onClick={handleGenerate}
            >
              쿼리 생성 및 SQL 검증
            </Button>

            {/* Error */}
            {error && <Alert type="error" message={error} showIcon />}

            {/* Result */}
            {result && (
              <Card
                size="small"
                title="생성된 쿼리"
                extra={
                  <Button
                    type="primary"
                    icon={<ArrowRightOutlined />}
                    onClick={handleOpenInPlayground}
                  >
                    Playground에서 열기
                  </Button>
                }
              >
                {result.explanation && (
                  <Alert
                    type="success"
                    message={result.explanation}
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                )}
                {result.sqlError && (
                  <Alert
                    type="error"
                    message="SQL 컴파일 실패"
                    description={result.sqlError}
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                )}
                <Space style={{ marginBottom: 8 }}>
                  <Button
                    icon={<CopyOutlined />}
                    onClick={() => copyToClipboard(formattedQuery, 'Cube.js Query가 복사되었습니다')}
                  >
                    Cube.js Query 복사
                  </Button>
                  {result.sql && (
                    <Button
                      icon={<CopyOutlined />}
                      onClick={() => copyToClipboard(result.sql || '', 'SQL이 복사되었습니다')}
                    >
                      SQL 복사
                    </Button>
                  )}
                </Space>
                <Text strong>Cube.js Query</Text>
                <pre
                  style={{
                    background: '#f5f5f5',
                    padding: 16,
                    borderRadius: 4,
                    overflow: 'auto',
                    fontSize: 13,
                    margin: '8px 0 16px',
                  }}
                >
                  {formattedQuery}
                </pre>
                {result.sql && (
                  <>
                    <Text strong>컴파일된 SQL</Text>
                    <pre
                      style={{
                        background: '#f5f5f5',
                        padding: 16,
                        borderRadius: 4,
                        overflow: 'auto',
                        fontSize: 13,
                        margin: '8px 0 0',
                      }}
                    >
                      {result.sql}
                    </pre>
                  </>
                )}
              </Card>
            )}
          </Space>
        </Card>
      </Content>
    </>
  );
}
