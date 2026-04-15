import React, { Component } from 'react';
import { Layout, Modal, Empty, Typography, Input, Button, Tooltip, Dropdown, message } from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  SaveOutlined,
  MoreOutlined,
} from '@ant-design/icons';
import Editor from '@monaco-editor/react';
import { RouterProps } from 'react-router-dom';

import { playgroundAction } from '../../events';
import { Menu, Tabs, Tree } from '../../components';
import { Alert, CubeLoader } from '../../atoms';
import { playgroundFetch } from '../../shared/helpers';
import { AppContext, AppContextConsumer } from '../../components/AppContext';
import { ButtonDropdown } from '../../QueryBuilder/ButtonDropdown';
import { SchemaFormat } from '../../types';

const { Content, Sider } = Layout;
const { TreeNode } = Tree;
const { TabPane } = Tabs;

const schemasMap = {};
const schemaToTreeData = (schemas) =>
  Object.keys(schemas).map((schemaName) => ({
    title: schemaName,
    key: schemaName,
    treeData: Object.keys(schemas[schemaName]).map((tableName) => {
      const key = `${schemaName}.${tableName}`;
      schemasMap[key] = [schemaName, tableName];
      return { title: tableName, key };
    }),
  }));

function getLanguage(fileName: string): string {
  if (fileName.endsWith('.yml') || fileName.endsWith('.yaml')) return 'yaml';
  if (fileName.endsWith('.js')) return 'javascript';
  return 'plaintext';
}

type SchemaPageProps = RouterProps;

export class SchemaPage extends Component<SchemaPageProps, any> {
  static contextType = AppContext;
  context!: React.ContextType<typeof AppContext>;

  constructor(props) {
    super(props);
    this.state = {
      expandedKeys: [],
      autoExpandParent: true,
      checkedKeys: [],
      selectedKeys: [],
      activeTab: 'schema',
      files: [],
      isDocker: null,
      shown: false,
      // editor
      selectedFile: null,
      editingContent: null,
      isDirty: false,
      saving: false,
      // modals
      newFileModal: false,
      newFileName: '',
      renameModal: false,
      renameTarget: null,
      renameNewName: '',
    };
  }

  async componentDidMount() {
    await this.loadDBSchema();
    await this.loadFiles();
  }

  onExpand(expandedKeys) {
    playgroundAction('Expand Tables');
    this.setState({ expandedKeys, autoExpandParent: false });
  }

  onCheck(checkedKeys) {
    playgroundAction('Check Tables');
    this.setState({ checkedKeys });
  }

  onSelect(selectedKeys) {
    this.setState({ selectedKeys });
  }

  async loadDBSchema() {
    this.setState({ schemaLoading: true });
    try {
      const res = await playgroundFetch('playground/db-schema');
      const result = await res.json();
      this.setState({ tablesSchema: result.tablesSchema });
    } catch (e: any) {
      this.setState({ schemaLoadingError: e });
    } finally {
      this.setState({ schemaLoading: false });
    }
  }

  async loadFiles() {
    const res = await playgroundFetch('playground/files');
    const result = await res.json();
    const files = result.files || [];
    this.setState({
      files,
      activeTab: files.length > 0 ? 'files' : 'schema',
    });
  }

  async generateSchema(format: SchemaFormat = SchemaFormat.js) {
    const { checkedKeys, tablesSchema } = this.state;
    const { history } = this.props;
    const options = { format };
    playgroundAction('Generate Schema', options);
    const res = await playgroundFetch('playground/generate-schema', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        format,
        tables: checkedKeys.filter((k) => !!schemasMap[k]).map((e) => schemasMap[e]),
        tablesSchema,
      }),
    });
    if (res.status === 200) {
      playgroundAction('Generate Schema Success', options);
      await this.loadFiles();
      this.setState({ checkedKeys: [], activeTab: 'files' });
      Modal.success({
        title: 'Data model files successfully generated!',
        content: 'You can start exploring your data model and building the charts',
        okText: 'Build',
        cancelText: 'Close',
        okCancel: true,
        onOk() { history.push('/build'); },
      });
    } else {
      playgroundAction('Generate Schema Fail', { error: await res.text(), ...options });
    }
  }

  selectFile(fileName: string) {
    const { files, isDirty, selectedFile } = this.state;
    if (isDirty && selectedFile) {
      Modal.confirm({
        title: 'Unsaved changes',
        content: `"${selectedFile}" has unsaved changes. Discard?`,
        okText: 'Discard',
        okType: 'danger',
        onOk: () => {
          const file = files.find((f) => f.fileName === fileName);
          this.setState({ selectedFile: fileName, editingContent: file?.content ?? '', isDirty: false });
        },
      });
    } else {
      const file = files.find((f) => f.fileName === fileName);
      this.setState({ selectedFile: fileName, editingContent: file?.content ?? '', isDirty: false });
    }
  }

  async saveFile() {
    const { selectedFile, editingContent, files } = this.state;
    if (!selectedFile) return;
    const prevContent = files.find((f) => f.fileName === selectedFile)?.content ?? '';
    this.setState({ saving: true });
    try {
      await playgroundFetch('playground/model/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fileName: selectedFile, content: editingContent }),
      });
      this.setState((prev) => ({
        files: prev.files.map((f) =>
          f.fileName === selectedFile ? { ...f, content: editingContent } : f
        ),
        isDirty: false,
      }));
      playgroundAction('Save Model File');
      // 저장 후 컴파일 결과 폴링 (최대 5회 × 1.5초)
      for (let i = 0; i < 5; i++) {
        await new Promise((r) => setTimeout(r, 1500));
        try {
          const metaRes = await fetch('/cubejs-api/v1/meta', {
            headers: { Authorization: '' },
          });
          const metaJson = await metaRes.json();
          if (metaJson.error) {
            // 에러 시 이전 내용으로 revert
            await playgroundFetch('playground/model/save', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ fileName: selectedFile, content: prevContent }),
            });
            this.setState((prev) => ({
              ...prev,
              files: prev.files.map((f) =>
                f.fileName === selectedFile ? { ...f, content: prevContent } : f
              ),
              editingContent: prevContent,
              isDirty: false,
            }));
            const errMsg = metaJson.error.replace(/Error: Compile errors:\nErrors:\n/, '').trim();
            message.error({ content: errMsg, duration: 10 });
            break;
          } else if (metaJson.cubes) {
            message.success('컴파일 성공');
            break;
          }
        } catch (_) {}
      }
    } finally {
      this.setState({ saving: false });
    }
  }

  async createFile() {
    const { newFileName } = this.state;
    const name = newFileName.trim();
    if (!name) return;
    const res = await playgroundFetch('playground/model/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fileName: name, content: '' }),
    });
    if (res.ok) {
      await this.loadFiles();
      this.setState({ newFileModal: false, newFileName: '' });
      this.selectFile(name);
      playgroundAction('Create Model File');
    } else {
      const { error } = await res.json();
      Modal.error({ title: 'Error', content: error });
    }
  }

  async deleteFile(fileName: string) {
    Modal.confirm({
      title: `Delete "${fileName}"?`,
      okText: 'Delete',
      okType: 'danger',
      onOk: async () => {
        await playgroundFetch('playground/model', {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ fileName }),
        });
        await this.loadFiles();
        if (this.state.selectedFile === fileName) {
          this.setState({ selectedFile: null, editingContent: null, isDirty: false });
        }
        playgroundAction('Delete Model File');
      },
    });
  }

  async renameFile() {
    const { renameTarget, renameNewName } = this.state;
    const newName = renameNewName.trim();
    if (!newName || !renameTarget) return;
    const res = await playgroundFetch('playground/model/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ oldFileName: renameTarget, newFileName: newName }),
    });
    if (res.ok) {
      await this.loadFiles();
      const { selectedFile } = this.state;
      if (selectedFile === renameTarget) {
        this.selectFile(newName);
      }
      this.setState({ renameModal: false, renameTarget: null, renameNewName: '' });
      playgroundAction('Rename Model File');
    } else {
      const { error } = await res.json();
      Modal.error({ title: 'Error', content: error });
    }
  }

  renderFilesMenu() {
    const { selectedFile, files } = this.state;
    return (
      <div>
        <div style={{ padding: '8px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontWeight: 500, fontSize: 12, color: '#8c8c8c' }}>MODEL FILES</span>
          <Tooltip title="New file">
            <Button
              type="text"
              size="small"
              icon={<PlusOutlined />}
              onClick={() => this.setState({ newFileModal: true })}
            />
          </Tooltip>
        </div>
        <Menu
          mode="inline"
          selectedKeys={selectedFile ? [selectedFile] : []}
        >
          {files.map((f) => (
            <Menu.Item
              key={f.fileName}
              onClick={() => this.selectFile(f.fileName)}
              style={{ paddingRight: 8 }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', flex: 1 }}>
                  {f.fileName}
                </span>
                <Dropdown
                  overlay={
                    <Menu>
                      <Menu.Item
                        icon={<EditOutlined />}
                        onClick={(e) => {
                          e.domEvent.stopPropagation();
                          this.setState({ renameModal: true, renameTarget: f.fileName, renameNewName: f.fileName });
                        }}
                      >
                        Rename
                      </Menu.Item>
                      <Menu.Item
                        icon={<DeleteOutlined />}
                        danger
                        onClick={(e) => {
                          e.domEvent.stopPropagation();
                          this.deleteFile(f.fileName);
                        }}
                      >
                        Delete
                      </Menu.Item>
                    </Menu>
                  }
                  trigger={['click']}
                >
                  <Button
                    type="text"
                    size="small"
                    icon={<MoreOutlined />}
                    onClick={(e) => e.stopPropagation()}
                    style={{ flexShrink: 0 }}
                  />
                </Dropdown>
              </div>
            </Menu.Item>
          ))}
        </Menu>
      </div>
    );
  }

  render() {
    const {
      schemaLoading,
      schemaLoadingError,
      tablesSchema,
      selectedFile,
      expandedKeys,
      autoExpandParent,
      checkedKeys,
      selectedKeys,
      activeTab,
      editingContent,
      isDirty,
      saving,
      newFileModal,
      newFileName,
      renameModal,
      renameNewName,
    } = this.state;

    const { playgroundContext } = this.context;
    const [major, minor] = playgroundContext.coreServerVersion
      ? playgroundContext.coreServerVersion.split('.')
      : [];
    const isYamlFormatSupported: boolean = (Number(major) > 0) || (!minor || Number(minor) >= 31);

    const renderTreeNodes = (data) =>
      data.map((item) => {
        if (item.treeData) {
          return (
            // @ts-ignore
            <TreeNode title={item.title} key={item.key} dataRef={item}>
              {renderTreeNodes(item.treeData)}
            </TreeNode>
          );
        }
        return <TreeNode {...item} />;
      });

    const renderTree = () =>
      Object.keys(tablesSchema || {}).length > 0 ? (
        <Tree
          checkable
          onExpand={this.onExpand.bind(this)}
          expandedKeys={expandedKeys}
          autoExpandParent={autoExpandParent}
          onCheck={this.onCheck.bind(this)}
          checkedKeys={checkedKeys}
          onSelect={this.onSelect.bind(this)}
          selectedKeys={selectedKeys}
        >
          {renderTreeNodes(schemaToTreeData(tablesSchema || {}))}
        </Tree>
      ) : (
        <Alert
          message="Empty DB Schema"
          description="Please check connection settings"
          type="warning"
        />
      );

    const renderTreeOrError = () =>
      schemaLoadingError ? (
        <Alert
          data-testid="schema-error"
          message="Error while loading DB schema"
          description={schemaLoadingError.toString()}
          type="error"
        />
      ) : (
        renderTree()
      );

    return (
      <Layout style={{ height: '100%' }}>
        <Sider width={340} className="schema-sidebar">
          <Tabs
            activeKey={activeTab}
            onChange={(tab) => this.setState({ activeTab: tab })}
            tabBarExtraContent={
              <ButtonDropdown
                show={this.state.shown}
                disabled={!checkedKeys.length}
                type="primary"
                data-testid="chart-type-btn"
                overlay={
                  <Menu data-testid="generate-schema">
                    <Menu.Item
                      title={!isYamlFormatSupported ? 'yaml schema format is supported by Cube 0.31.0 and later' : ''}
                      disabled={!isYamlFormatSupported}
                      onClick={() => this.generateSchema(SchemaFormat.yaml)}
                    >
                      YAML
                    </Menu.Item>
                    <Menu.Item onClick={() => this.generateSchema()}>
                      JavaScript
                    </Menu.Item>
                  </Menu>
                }
                style={{ border: 0 }}
                onOverlayOpen={() => this.setState({ shown: true })}
                onOverlayClose={() => this.setState({ shown: false })}
                onItemClick={() => this.setState({ shown: false })}
              >
                Generate Data Model
              </ButtonDropdown>
            }
          >
            <TabPane tab="Tables" key="schema">
              {schemaLoading ? <CubeLoader /> : renderTreeOrError()}
            </TabPane>
            <TabPane tab="Files" key="files">
              {this.renderFilesMenu()}
            </TabPane>
          </Tabs>
        </Sider>

        <Content style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          {selectedFile ? (
            <>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 16px',
                borderBottom: '1px solid #f0f0f0',
                background: '#fafafa',
              }}>
                <Typography.Text strong style={{ fontSize: 13 }}>
                  {selectedFile}
                  {isDirty && <span style={{ color: '#faad14', marginLeft: 6 }}>●</span>}
                </Typography.Text>
                <Button
                  type="primary"
                  size="small"
                  icon={<SaveOutlined />}
                  loading={saving}
                  disabled={!isDirty}
                  onClick={() => this.saveFile()}
                >
                  Save
                </Button>
              </div>
              <div style={{ flex: 1, overflow: 'hidden' }}>
                <Editor
                  height="100%"
                  language={getLanguage(selectedFile)}
                  value={editingContent ?? ''}
                  theme="vs-dark"
                  onChange={(value) => this.setState({ editingContent: value ?? '', isDirty: true })}
                  options={{
                    minimap: { enabled: false },
                    fontSize: 13,
                    lineNumbers: 'on',
                    wordWrap: 'on',
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                  }}
                />
              </div>
            </>
          ) : (
            <Empty
              style={{ marginTop: 80 }}
              description="Select a file to edit, or create a new one"
            />
          )}
        </Content>

        {/* New File Modal */}
        <Modal
          title="New Model File"
          visible={newFileModal}
          onOk={() => this.createFile()}
          onCancel={() => this.setState({ newFileModal: false, newFileName: '' })}
          okText="Create"
        >
          <Input
            placeholder="e.g. cubes/orders.yml"
            value={newFileName}
            onChange={(e) => this.setState({ newFileName: e.target.value })}
            onPressEnter={() => this.createFile()}
            autoFocus
          />
        </Modal>

        {/* Rename Modal */}
        <Modal
          title="Rename File"
          visible={renameModal}
          onOk={() => this.renameFile()}
          onCancel={() => this.setState({ renameModal: false, renameTarget: null, renameNewName: '' })}
          okText="Rename"
        >
          <Input
            value={renameNewName}
            onChange={(e) => this.setState({ renameNewName: e.target.value })}
            onPressEnter={() => this.renameFile()}
            autoFocus
          />
        </Modal>

        <AppContextConsumer
          onReady={({ playgroundContext: ctx }) =>
            this.setState({ isDocker: ctx?.isDocker })
          }
        />
      </Layout>
    );
  }
}
