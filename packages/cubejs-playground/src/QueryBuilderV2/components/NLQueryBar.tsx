import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Button,
  CloseIcon,
  Panel,
  SearchInput,
  Space,
  Tag,
  tasty,
  Text,
  TextArea,
  TooltipProvider,
} from '@cube-dev/ui-kit';
import { RobotOutlined } from '@ant-design/icons';

import { useQueryBuilderContext } from '../context';
import { useEvent } from '../hooks';

const NLBar = tasty(Panel, {
  styles: {
    fill: '#purple.04',
    border: 'bottom',
    padding: '1x',
    gap: '1x',
    flow: 'column',
  },
});

const CubeTag = tasty(Tag, {
  styles: {
    fill: '#purple.12',
    border: '#purple.24',
    color: '#purple',
    radius: '1r',
    padding: '0 .5x',
    fontSize: '.8em',
  },
});

const CubePickerPanel = tasty(Panel, {
  styles: {
    position: 'absolute',
    top: '100%',
    left: 0,
    zIndex: 100,
    fill: '#white',
    border: '1bw',
    radius: '1r',
    shadow: '0 4px 16px #dark.12',
    width: '240px',
    maxHeight: '280px',
    flow: 'column',
    gap: 0,
  },
});

const ExplanationText = tasty(Text, {
  styles: {
    color: '#success-text',
    fontSize: '.8em',
  },
});

const ErrorText = tasty(Text, {
  styles: {
    color: '#danger-text',
    fontSize: '.8em',
  },
});

export function NLQueryBar() {
  const {
    cubes,
    nlSelectedCubes,
    toggleNLCube,
    clearNLCubes,
    setQuery,
    runQuery,
    apiUrl,
    apiToken,
  } = useQueryBuilderContext();

  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [explanation, setExplanation] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerSearch, setPickerSearch] = useState('');
  const pickerRef = useRef<HTMLDivElement>(null);

  const allCubes = cubes ?? [];
  const filteredPickerCubes = pickerSearch
    ? allCubes.filter(
        (c) =>
          c.name.toLowerCase().includes(pickerSearch.toLowerCase()) ||
          c.title.toLowerCase().includes(pickerSearch.toLowerCase())
      )
    : allCubes;

  // Close picker on outside click
  useEffect(() => {
    if (!pickerOpen) return;

    function handleClick(e: MouseEvent) {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setPickerOpen(false);
        setPickerSearch('');
      }
    }

    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [pickerOpen]);

  const handleSubmit = useEvent(async () => {
    if (!input.trim() || !apiUrl || !apiToken) return;

    setIsLoading(true);
    setError(null);
    setExplanation(null);

    try {
      const baseUrl = apiUrl.replace(/\/cubejs-api\/v1\/?$/, '');
      const response = await fetch(`${baseUrl}/cubejs-api/v1/nl/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${apiToken}`,
        },
        body: JSON.stringify({
          naturalLanguage: input.trim(),
          cubeNames: nlSelectedCubes.length > 0 ? nlSelectedCubes : undefined,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.error?.message || 'Failed to generate query');
      }

      setQuery(data.query);
      setExplanation(data.explanation ?? null);
      void runQuery();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  });

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        void handleSubmit();
      }
    },
    [handleSubmit]
  );

  const selectedCubeObjects = allCubes.filter((c) => nlSelectedCubes.includes(c.name));

  return (
    <NLBar>
      {/* Cube/View selector row */}
      <Space gap=".5x" placeItems="center start" style={{ flexWrap: 'wrap' }}>
        <Text preset="c2" color="#purple-text">
          <RobotOutlined /> Context:
        </Text>

        {selectedCubeObjects.map((cube) => (
          <CubeTag key={cube.name}>
            {cube.title}
            <Button
              size="small"
              type="clear"
              icon={<CloseIcon />}
              aria-label={`Remove ${cube.title}`}
              styles={{ padding: 0, minWidth: 'unset', height: 'unset' }}
              onPress={() => toggleNLCube(cube.name)}
            />
          </CubeTag>
        ))}

        <div style={{ position: 'relative' }} ref={pickerRef}>
          <Button
            qa="NLAddCubeButton"
            size="small"
            type="outline"
            onPress={() => setPickerOpen((v) => !v)}
          >
            + Add cube/view
          </Button>

          {pickerOpen && (
            <CubePickerPanel>
              <div style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-color)' }}>
                <SearchInput
                  size="small"
                  isClearable
                  aria-label="Search cubes"
                  placeholder="Search..."
                  value={pickerSearch}
                  onChange={setPickerSearch}
                />
              </div>
              <div style={{ overflowY: 'auto', maxHeight: '220px' }}>
                {filteredPickerCubes.length === 0 ? (
                  <div style={{ padding: '6px 8px', fontSize: '12px', color: '#888' }}>
                    No results
                  </div>
                ) : (
                  filteredPickerCubes.map((cube) => (
                    <div
                      key={cube.name}
                      onClick={() => toggleNLCube(cube.name)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '5px 10px',
                        cursor: 'pointer',
                        fontSize: '13px',
                        backgroundColor: 'transparent',
                      }}
                      onMouseEnter={(e) => {
                        (e.currentTarget as HTMLDivElement).style.backgroundColor =
                          'rgba(124,77,255,0.08)';
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLDivElement).style.backgroundColor = 'transparent';
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={nlSelectedCubes.includes(cube.name)}
                        onChange={() => {}}
                        onClick={(e) => e.stopPropagation()}
                        style={{ pointerEvents: 'none', accentColor: '#7c4dff' }}
                      />
                      <span>{cube.title}</span>
                    </div>
                  ))
                )}
              </div>
              {nlSelectedCubes.length > 0 && (
                <div style={{ padding: '6px 8px', borderTop: '1px solid var(--border-color)' }}>
                  <Button size="small" type="clear" onPress={clearNLCubes}>
                    Clear all
                  </Button>
                </div>
              )}
            </CubePickerPanel>
          )}
        </div>

        {nlSelectedCubes.length > 0 && (
          <TooltipProvider title="Clear cube selection">
            <Button
              size="small"
              type="clear"
              theme="danger"
              icon={<CloseIcon />}
              onPress={clearNLCubes}
            />
          </TooltipProvider>
        )}
      </Space>

      {/* NL input row */}
      <Space gap="1x" placeItems="end">
        <TextArea
          qa="NLQueryInput"
          aria-label="Natural language query"
          placeholder='e.g. "Show me total revenue by country for the last 30 days"'
          value={input}
          rows={2}
          styles={{ flexGrow: 1 }}
          onChange={(val: string) => {
            setInput(val);
            setError(null);
            setExplanation(null);
          }}
          onKeyDown={handleKeyDown}
        />
        <TooltipProvider
          title={
            <>
              <kbd>⌘</kbd> + <kbd>Enter</kbd>
            </>
          }
        >
          <Button
            qa="NLGenerateButton"
            type="primary"
            size="small"
            isDisabled={!input.trim() || isLoading}
            isLoading={isLoading}
            icon={<RobotOutlined />}
            onPress={handleSubmit}
          >
            Generate
          </Button>
        </TooltipProvider>
      </Space>

      {/* Feedback row */}
      {explanation && <ExplanationText>✓ {explanation}</ExplanationText>}
      {error && <ErrorText>✗ {error}</ErrorText>}
    </NLBar>
  );
}
