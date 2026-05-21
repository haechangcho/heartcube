import { LogoutOutlined, MenuOutlined, RobotOutlined } from '@ant-design/icons';
import { Dropdown, Menu } from 'antd';
import { useMediaQuery } from 'react-responsive';
import { Link } from 'react-router-dom';
import styled from 'styled-components';

import { useAppContext } from '../../hooks';
import { StyledMenu, StyledMenuItem } from './Menu';

const HeaderDropdown = Dropdown as any;

const StyledHeader = styled.div`
  && {
    background-color: var(--dark-02-color);
    color: white;
    padding: 0 132px 0 16px;
    line-height: 44px;
    height: 48px;
    position: relative;

    .logout-button {
      position: absolute;
      top: 8px;
      right: 16px;
      z-index: 10;
      height: 32px;
      border: 1px solid rgba(255, 255, 255, 0.35);
      border-radius: 4px;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: transparent;
      color: white;
      cursor: pointer;
      transition: all 0.25s ease;
      padding: 0 10px;
      font-size: 14px;
      line-height: 30px;
    }

    .logout-button:hover {
      border-color: white;
      color: white;
    }
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

          <StyledMenuItem key="/connection">
            <Link to="/connection">Connections</Link>
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
        <button
          className="logout-button"
          type="button"
          title={userLabel}
          onClick={logout}
        >
          <LogoutOutlined />
          <span>Logout</span>
        </button>
      )}

      {isMobileOrTable && (
        <div style={{ float: 'right' }}>
          <HeaderDropdown
            overlay={
              <Menu>
                <Menu.Item key="/build">
                  <Link to="/build">Playground</Link>
                </Menu.Item>

                <Menu.Item key="/schema">
                  <Link to="/schema">Data Model</Link>
                </Menu.Item>

                <Menu.Item key="/connection">
                  <Link to="/connection">Connections</Link>
                </Menu.Item>

                <Menu.Item key="/logout" onClick={logout}>
                  Logout
                </Menu.Item>
              </Menu>
            }
          >
            <MenuOutlined />
          </HeaderDropdown>
        </div>
      )}
    </StyledHeader>
  );
}
