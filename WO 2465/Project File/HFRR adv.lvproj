<?xml version='1.0' encoding='UTF-8'?>
<Project Type="Project" LVVersion="25008000">
	<Property Name="NI.LV.All.SaveVersion" Type="Str">25.0</Property>
	<Property Name="NI.LV.All.SourceOnly" Type="Bool">true</Property>
	<Item Name="My Computer" Type="My Computer">
		<Property Name="server.app.propertiesEnabled" Type="Bool">true</Property>
		<Property Name="server.control.propertiesEnabled" Type="Bool">true</Property>
		<Property Name="server.tcp.enabled" Type="Bool">false</Property>
		<Property Name="server.tcp.port" Type="Int">0</Property>
		<Property Name="server.tcp.serviceName" Type="Str">My Computer/VI Server</Property>
		<Property Name="server.tcp.serviceName.default" Type="Str">My Computer/VI Server</Property>
		<Property Name="server.vi.callsEnabled" Type="Bool">true</Property>
		<Property Name="server.vi.propertiesEnabled" Type="Bool">true</Property>
		<Property Name="specify.custom.address" Type="Bool">false</Property>
		<Item Name="icon file" Type="Folder" URL="../../icon file">
			<Property Name="NI.DISK" Type="Bool">true</Property>
		</Item>
		<Item Name="HFRR ADV v05.vi" Type="VI" URL="../../HFRR ADV v05.vi"/>
		<Item Name="HFRR ADV v06.vi" Type="VI" URL="../../HFRR ADV v06.vi"/>
		<Item Name="HFRR ADV v07.vi" Type="VI" URL="../../HFRR ADV v07.vi"/>
		<Item Name="HFRR ADV v08.vi" Type="VI" URL="../../HFRR ADV v08.vi"/>
		<Item Name="HFRR ADV v09.vi" Type="VI" URL="../../HFRR ADV v09.vi"/>
		<Item Name="HFRR ADV v10.vi" Type="VI" URL="../../HFRR ADV v10.vi"/>
		<Item Name="HFRR ADV v12.vi" Type="VI" URL="../../HFRR ADV v12.vi"/>
		<Item Name="Dependencies" Type="Dependencies"/>
		<Item Name="Build Specifications" Type="Build">
			<Item Name="LAB-IQ adv" Type="EXE">
				<Property Name="App_copyErrors" Type="Bool">true</Property>
				<Property Name="App_INI_aliasGUID" Type="Str">{14B7B166-9EE7-4D40-9D0B-6FF47BF44682}</Property>
				<Property Name="App_INI_GUID" Type="Str">{52A57C3C-6428-468B-B632-BB547DC9CAF8}</Property>
				<Property Name="App_serverConfig.httpPort" Type="Int">8002</Property>
				<Property Name="App_serverType" Type="Int">0</Property>
				<Property Name="Bld_autoIncrement" Type="Bool">true</Property>
				<Property Name="Bld_buildCacheID" Type="Str">{365F07C5-6D6B-45BE-821C-4250C4695205}</Property>
				<Property Name="Bld_buildSpecName" Type="Str">LAB-IQ adv</Property>
				<Property Name="Bld_excludeInlineSubVIs" Type="Bool">true</Property>
				<Property Name="Bld_excludeLibraryItems" Type="Bool">true</Property>
				<Property Name="Bld_excludePolymorphicVIs" Type="Bool">true</Property>
				<Property Name="Bld_localDestDir" Type="Path">../builds/exe/v12</Property>
				<Property Name="Bld_localDestDirType" Type="Str">relativeToCommon</Property>
				<Property Name="Bld_modifyLibraryFile" Type="Bool">true</Property>
				<Property Name="Bld_previewCacheID" Type="Str">{E5602A09-287A-447A-9CF0-41DE9F7E2566}</Property>
				<Property Name="Bld_version.build" Type="Int">46</Property>
				<Property Name="Bld_version.major" Type="Int">1</Property>
				<Property Name="Destination[0].destName" Type="Str">LAB-IQ adv.exe</Property>
				<Property Name="Destination[0].path" Type="Path">../builds/exe/v12/LAB-IQ adv.exe</Property>
				<Property Name="Destination[0].preserveHierarchy" Type="Bool">true</Property>
				<Property Name="Destination[0].type" Type="Str">App</Property>
				<Property Name="Destination[1].destName" Type="Str">Support Directory</Property>
				<Property Name="Destination[1].path" Type="Path">../builds/exe/v12/data</Property>
				<Property Name="DestinationCount" Type="Int">2</Property>
				<Property Name="Exe_iconItemID" Type="Ref">/My Computer/icon file/02-FR5.12.ico</Property>
				<Property Name="Source[0].itemID" Type="Str">{54F6D361-64DA-4D0C-928B-373B62038F11}</Property>
				<Property Name="Source[0].type" Type="Str">Container</Property>
				<Property Name="Source[1].destinationIndex" Type="Int">0</Property>
				<Property Name="Source[1].itemID" Type="Ref">/My Computer/HFRR ADV v05.vi</Property>
				<Property Name="Source[1].type" Type="Str">VI</Property>
				<Property Name="Source[2].destinationIndex" Type="Int">0</Property>
				<Property Name="Source[2].itemID" Type="Ref">/My Computer/HFRR ADV v06.vi</Property>
				<Property Name="Source[2].type" Type="Str">VI</Property>
				<Property Name="Source[3].destinationIndex" Type="Int">0</Property>
				<Property Name="Source[3].itemID" Type="Ref">/My Computer/HFRR ADV v07.vi</Property>
				<Property Name="Source[3].type" Type="Str">VI</Property>
				<Property Name="Source[4].destinationIndex" Type="Int">0</Property>
				<Property Name="Source[4].itemID" Type="Ref">/My Computer/HFRR ADV v08.vi</Property>
				<Property Name="Source[4].type" Type="Str">VI</Property>
				<Property Name="Source[5].destinationIndex" Type="Int">0</Property>
				<Property Name="Source[5].itemID" Type="Ref">/My Computer/HFRR ADV v09.vi</Property>
				<Property Name="Source[5].type" Type="Str">VI</Property>
				<Property Name="Source[6].destinationIndex" Type="Int">0</Property>
				<Property Name="Source[6].itemID" Type="Ref">/My Computer/HFRR ADV v10.vi</Property>
				<Property Name="Source[6].type" Type="Str">VI</Property>
				<Property Name="Source[7].destinationIndex" Type="Int">0</Property>
				<Property Name="Source[7].itemID" Type="Ref">/My Computer/HFRR ADV v12.vi</Property>
				<Property Name="Source[7].sourceInclusion" Type="Str">TopLevel</Property>
				<Property Name="Source[7].type" Type="Str">VI</Property>
				<Property Name="SourceCount" Type="Int">8</Property>
				<Property Name="TgtF_fileDescription" Type="Str">LAB-IQ adv</Property>
				<Property Name="TgtF_internalName" Type="Str">LAB-IQ adv</Property>
				<Property Name="TgtF_legalCopyright" Type="Str">Copyright © 2026 </Property>
				<Property Name="TgtF_productName" Type="Str">LAB-IQ adv</Property>
				<Property Name="TgtF_targetfileGUID" Type="Str">{428DEFF7-A100-456E-8584-372790858B16}</Property>
				<Property Name="TgtF_targetfileName" Type="Str">LAB-IQ adv.exe</Property>
				<Property Name="TgtF_versionIndependent" Type="Bool">true</Property>
			</Item>
		</Item>
	</Item>
</Project>
