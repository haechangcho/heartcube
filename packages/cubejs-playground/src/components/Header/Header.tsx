import { LogoutOutlined, MenuOutlined, RobotOutlined } from '@ant-design/icons';
import { Dropdown, Layout, Menu } from 'antd';
import { useMediaQuery } from 'react-responsive';
import { Link } from 'react-router-dom';
import styled from 'styled-components';

import { useAppContext } from '../../hooks';
import { StyledMenu, StyledMenuButton, StyledMenuItem } from './Menu';

const StyledHeader = styled(Layout.Header)`
  && {
    background-color: var(--dark-02-color);
    color: white;
    padding: 0 16px;
    line-height: 44px;
    height: 48px;
  }
`;

type Props = {
  selectedKeys: string[];
};

export default function Header({ selectedKeys }: Props) {
  const { playgroundContext } = useAppContext();
  const isDesktopOrLaptop = useMediaQuery({
    query: '(min-width: 992px)',
  });

  const isMobileOrTable = useMediaQuery({
    query: '(max-width: 991px)',
  });

  const userLabel = playgroundContext?.securityContext
    ? `${playgroundContext.securityContext.sub} / ${playgroundContext.securityContext.groups.join(',')}`
    : 'Logout';

  async function logout() {
    await fetch('/logout', { method: 'POST' }).catch(() => null);
    window.location.assign('/login');
  }

  return (
    <StyledHeader>
      <div style={{ float: 'left' }}>
        <img
          src="./cube-core-logo-adapted_for_dark_bg.svg"
          style={{ height: 28, marginRight: 28 }}
          alt=""
        />
      </div>

      {isDesktopOrLaptop && (
        <StyledMenu theme="light" mode="horizontal" selectedKeys={selectedKeys}>
          <StyledMenuItem key="/build">
            <Link to="/build">Playground</Link>
          </StyledMenuItem>

          <StyledMenuItem key="/schema">
            <Link to="/schema">Data Model</Link>
          </StyledMenuItem>

          <StyledMenuItem key="/frontend-integrations">
            <Link to="/frontend-integrations">Frontend Integrations</Link>
          </StyledMenuItem>

          <StyledMenuItem key="/ask-ai">
            <Link to="/ask-ai"><RobotOutlined style={{ marginRight: 6 }} />Ask AI</Link>
          </StyledMenuItem>

          <StyledMenuItem key="/hc-analytics">
            <a href="https://stg.heartcount.io/" target="_blank" rel="noreferrer">HC Analytics</a>
          </StyledMenuItem>
        </StyledMenu>
      )}

      {isDesktopOrLaptop && (
        <StyledMenuButton
          as="button"
          type="button"
          title={userLabel}
          onClick={logout}
          noMargin
        >
          <LogoutOutlined />
          <span>Logout</span>
        </StyledMenuButton>
      )}

      {isMobileOrTable && (
        <div style={{ float: 'right' }}>
          <Dropdown
            overlay={
              <Menu>
                <Menu.Item key="/build">
                  <Link to="/build">Playground</Link>
                </Menu.Item>

                <Menu.Item key="/schema">
                  <Link to="/schema">Data Model</Link>
                </Menu.Item>

                <Menu.Item key="/logout" onClick={logout}>
                  Logout
                </Menu.Item>
              </Menu>
            }
          >
            <MenuOutlined />
          </Dropdown>
        </div>
      )}
    </StyledHeader>
  );
}
